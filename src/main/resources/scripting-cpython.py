'''scripting-cpython.py - Attach to Java CPython scripting

scripting-cpython is licensed under the BSD license.  See the
accompanying file LICENSE for details.

 Copyright (C) 2009 - 2014 Board of Regents of the University of
 Wisconsin-Madison, Broad Institute of MIT and Harvard, and Max Planck
 Institute of Molecular Cell Biology and Genetics.
 All rights reserved.

'''

import ast
import inspect
import javabridge as J
import threading
import logging
import numpy as np
import sys
logger = logging.getLogger(__name__)

def engine_requester():
    J.attach()
    while True:
        try:
            msg = J.run_script(
            """importPackage(Packages.org.scijava.plugins.scripting.cpython);
               CPythonScriptEngine.engineRequestQueue.take();""")
            if logger.level <= logging.INFO:
                logger.info("Received engine request: %s",
                            J.to_string(msg))
            payload = J.get_collection_wrapper(
                J.run_script("msg.payload", dict(msg=msg)))
            if J.run_script(
                """importPackage(Packages.org.scijava.plugins.scripting.cpython);
                msg.command==CPythonScriptEngine.EngineCommands.NEW_ENGINE;
                """, dict(msg=msg)):
                do_new_engine(payload)
            elif J.run_script(
                """importPackage(Packages.org.scijava.plugins.scripting.cpython);
                msg.command==CPythonScriptEngine.EngineCommands.CLOSE_SERVICE;
                """, dict(msg=msg)):
                logger.info("Exiting script service thread in response to "
                            "termination request")
                break
            else:
                J.run_script(
                """importPackage(Packages.org.scijava.plugins.scripting.cpython);
                var exception = new java.lang.RuntimeException(
                    java.lang.String.format('Unknown command: %s', msg.command.toString()));
                var payload = new java.util.ArrayList();
                payload.add(exception);
                var response = new CPythonScriptEngine.Message(
                    CPythonScriptEngine.EngineCommands.EXCEPTION, payload);
                CPythonScriptEngine.engineResponseQueue.put(response);
                """)
        except:
            # To do: how to handle failure, probably from .take()
            # Guessing that someone has managed to interrupt our thread
            logger.warn("Exiting script service thread", exc_info=True)
    J.detach()
            
def engine(q_request, q_response):
    logger.info("Starting script engine thread")
    J.attach()
    while True:
        try:
            msg = J.run_script(
            """importPackage(Packages.org.scijava.plugins.scripting.cpython);
               q_request.take();""", dict(q_request=q_request))
            if logger.level <= logging.INFO:
                logger.info("Received engine request: %s",
                            J.to_string(msg))
            payload = J.get_collection_wrapper(
                J.run_script("msg.payload", dict(msg=msg)))
            if J.run_script(
                """importPackage(Packages.org.scijava.plugins.scripting.cpython);
                msg.command==CPythonScriptEngine.EngineCommands.EXECUTE;
                """, dict(msg=msg)):
                response = do_execute(payload)
            elif J.run_script(
                """importPackage(Packages.org.scijava.plugins.scripting.cpython);
                msg.command==CPythonScriptEngine.EngineCommands.EVALUATE;
                """, dict(msg=msg)):
                response = do_evaluate(payload)
            elif J.run_script(
                """importPackage(Packages.org.scijava.plugins.scripting.cpython);
                msg.command==CPythonScriptEngine.EngineCommands.CLOSE_ENGINE;
                """, dict(msg=msg)):
                logger.info("Exiting script engine thread after close request")
                break
            else:
                logger.warn(
                    "Received unknown command: %s" %
                    J.run_script("msg.command.toString()", dict(msg=msg)))
                response = J.run_script(
                """importPackage(Packages.org.scijava.plugins.scripting.cpython);
                var exception = new java.lang.RuntimeException(
                    java.lang.String.format('Unknown command: %s', msg.command.toString()));
                var payload = new java.util.ArrayList();
                payload.add(exception);
                new CPythonScriptEngine.Message(
                    CPythonScriptEngine.EngineCommands.EXCEPTION, payload);
                """, dict(msg=msg))
            J.run_script("q_response.put(response);", 
                         dict(q_response=q_response,
                              response=response))
        except:
            # To do: how to handle failure, probably from .take()
            # Guessing that someone has managed to interrupt our thread
            logger.warn("Exiting script engine thread", exc_info=True)
    J.detach()
    
def do_new_engine(payload):
    '''Create a new engine thread
    
    payload: first member is request queue, second is response queue
    '''
    logger.info("Creating new engine")
    thread = threading.Thread(target = engine, args=list(payload[:2]),
                              name = "Scripting-CPythonEngine")
    thread.setDaemon(True)
    thread.start()
    J.run_script(
    """importPackage(Packages.org.scijava.plugins.scripting.cpython);
    var payload = new java.util.ArrayList();
    var response = new CPythonScriptEngine.Message(
        CPythonScriptEngine.EngineCommands.NEW_ENGINE_RESULT, payload);
    CPythonScriptEngine.engineResponseQueue.put(response);
    """)
    
def do_evaluate(payload):
    '''Evaluate a Python command
    
    payload: first member is Python command string, second is local context
    '''
    logger.info("Evaluating script")
    filename = "scripting-cpython"
    try:
        command = J.to_string(payload[0])
        context = context_to_locals(payload[1])
        logger.debug("Script:\n%s" % command)
        #
        # OK, the game plan is a little difficult here:
        #
        # use AST to parse (see https://docs.python.org/2.7/library/ast.html)
        # The AST object's body is a list of statements.
        # If the last body element is an ast.Expr, then
        # we execute all of the statements except the last
        # and then we wrap the last as an ast.Expression
        # and evaluate it.
        #
        a = ast.parse(command)
        if isinstance(a.body[-1], ast.Expr):
            expr = a.body[-1]
            del a.body[-1]
        else:
            expr = a.parse("None").body[0]
        
        filename = context.get("javax.scripting.filename", 
                               "scripting-cpython") 
        code = compile(a, filename, mode="exec")
        exec(code, __builtins__.__dict__, context)
        code = compile(ast.Expression(expr.value), filename, mode="eval")
        result = eval(code, __builtins__.__dict__, context)
        logger.debug("Script evaluated")
        return J.run_script(
            """importPackage(Packages.org.scijava.plugins.scripting.cpython);
            var payload = new java.util.ArrayList();
            payload.add(result);
            new CPythonScriptEngine.Message(
                CPythonScriptEngine.EngineCommands.EVALUATE_RESULT, payload);
            """, dict(result=result))
    except:
        logger.info("Exception caught during eval", exc_info=True)
        e_type, e, e_tb = sys.exc_info()
        
        return J.run_script(
            """
            importPackage(Packages.org.scijava.plugins.scripting.cpython);
            var exception = new javax.script.ScriptException(
                java.lang.String.format('Python exception: %s', e),
                filename, line_number);
            var payload = new java.util.ArrayList();
            payload.add(exception);
            new CPythonScriptEngine.Message(
               CPythonScriptEngine.EngineCommands.EXCEPTION, payload);
            """, dict(e=repr(e), filename = filename, 
                      line_number = e_tb.tb_lineno))

def context_to_locals(context):
    '''convert the local context as a Java map to a dictionary of locals'''
    d = { "JWrapper": JWrapper,
          "importClass": importClass }
    m = J.get_map_wrapper(context)
    for k in m:
        key = J.to_string(k)
        o = m[k]
        if isinstance(o, J.JB_Object):
            if J.is_instance_of(o, "java/lang/String"):
                d[key] = J.to_string(o)
                continue
            for class_name, method, signature in (
                ("java/lang/Boolean", "booleanValue", "()Z"),
                ("java/lang/Byte", "byteValue", "()B"),
                ("java/lang/Integer",  "intValue", "()I"),
                ("java/lang/Long", "longValue", "()L"),
                ("java/lang/Float", "floatValue", "()F"),
                ("java/lang/Double", "doubleValue", "()D")):
                if J.is_instance_of(o, class_name):
                    d[key] = J.call(o, method, signature)
                    break
            else:
                d[key] = JWrapper(o)
        else:
            d[key] = o
            
    return d

class JWrapper(object):
    '''A class that wraps a Java object
    
    Usage:
    >>> a = JWrapper(javabridge.make_instance("java/util/ArrayList", "()V"))
    >>> a.add("Hello")
    >>> a.add("World")
    >>> a.size()
    2
    '''
    def __init__(self, o):
        '''Initialize the JWrapper with a Java object
        
        :param o: a Java object (class = JB_Object)
        '''
        STATIC = J.get_static_field("java/lang/reflect/Modifier", "STATIC", "I")
        self.o = o
        self.class_wrapper = J.get_class_wrapper(o)
        env = J.get_env()
        methods = env.get_object_array_elements(self.class_wrapper.getMethods())
        self.methods = {}
        for jmethod in methods:
            if (J.call(jmethod, "getModifiers", "()I") & STATIC) == STATIC:
                continue
            method = J.get_method_wrapper(jmethod)
            name = method.getName()
            if name not in self.methods:
                self.methods[name] = []
                fn = lambda naame=name: lambda *args: self.__call(naame, *args)
                fn = fn()
                fn.__doc__ = J.to_string(jmethod)
                setattr(self, name, fn)
            else:
                fn = getattr(self, name)
                fn.__doc__ = fn.__doc__ +"\n"+J.to_string(jmethod)
            self.methods[name].append(method)
        jfields = self.class_wrapper.getFields()
        fields = env.get_object_array_elements(jfields)
        
    def __getattr__(self, name):
        try:
            jfield = self.klass.getField(name)
        except:
            raise AttributeError()
    
        STATIC = J.get_static_field("java/lang/reflect/Modifier", "STATIC", "I")
        if (J.call(jfield, "getModifiers", "()I") & STATIC) == STATIC:
            raise AttributeError()
        klass = J.call(jfield, "getType", "()Ljava/lang/Class;")
        result = J.get_field(self.o, name, sig(klass))
        if isinstance(result, J.JB_Object):
            result = JWrapper(result)
        return result
    
    def __setattr__(self, name, value):
        try:
            jfield = self.klass.getField(name)
        except:
            object.__setattr__(self, name, value)
            return
    
        STATIC = J.get_static_field("java/lang/reflect/Modifier", "STATIC", "I")
        if (J.call(jfield, "getModifiers", "()I") & STATIC) == STATIC:
            raise AttributeError()
        klass = J.call(jfield, "getType", "()Ljava/lang/Class;")
        result = J.set_field(self.o, name, sig(klass), value)
            
    def __call(self, method_name, *args):
        '''Call the appropriate overloaded method with the given name
        
        :param method_name: the name of the method to call
        :param *args: the arguments to the method, which are used to
                      disambiguate between similarly named methods
        '''
        env = J.get_env()
        last_e = None
        for method in self.methods[method_name]:
            params = env.get_object_array_elements(method.getParameterTypes())
            is_var_args = J.call(method.o, "isVarArgs", "()Z")
            if len(args) < len(params) - (1 if is_var_args else 0):
                continue
            if len(args) > len(params) and not is_var_args:
                continue
            if is_var_args:
                pm1 = len(params)-1
                args1 = args[:pm1] + [args[pm1:]]
            else:
                args1 = args
            try:
                cargs = [cast(o, klass) for o, klass in zip(args1, params)]
            except:
                last_e = sys.exc_info()[1]
                continue
            rtype = J.call(method.o, "getReturnType", "()Ljava/lang/Class;")
            args_sig = "".join(map(sig, params))
            rsig = sig(rtype)
            msig = "(%s)%s" % (args_sig, rsig)
            result =  J.call(self.o, method_name, msig, *cargs)
            if isinstance(result, J.JB_Object):
                result = JWrapper(result)
            return result
        raise TypeError("No matching method found for %s" % method_name)
    
    def __repr__(self):
        classname = J.call(J.call(self.o, "getClass", "()Ljava/lang/Class;"), 
                           "getName", "()Ljava/lang/String;")
        return "Instance of %s: %s" % (classname, J.to_string(self.o))
    
    def __str__(self):
        return J.to_string(self.o)

class JClassWrapper(object):
    '''Wrapper for a class
    
    >>> Integer = JClassWrapper("java.lang.Integer")
    >>> Integer.MAX_VALUE
    2147483647
    '''
    def __init__(self, class_name):
        '''Initialize to wrap a class name
        
        :param class_name: name of class in dotted form, e.g. java.lang.Integer
        '''
        STATIC = J.get_static_field("java/lang/reflect/Modifier", "STATIC", "I")
        self.cname = class_name.replace(".", "/")
        self.klass = J.get_class_wrapper(J.class_for_name(class_name), True)
        self.static_methods = {}
        methods = env.get_object_array_elements(self.klass.getMethods())
        self.methods = {}
        for jmethod in methods:
            if (J.call(jmethod, "getModifiers", "()I") & STATIC) != STATIC:
                continue
            method = J.get_method_wrapper(jmethod)
            name = method.getName()
            if name not in self.methods:
                self.methods[name] = []
                fn = lambda naame=name: lambda *args: self.__call_static(naame, *args)
                fn = fn()
                fn.__doc__ = J.to_string(jmethod)
                setattr(self, name, fn)
            else:
                fn = getattr(self, name)
                fn.__doc__ = fn.__doc__ +"\n"+J.to_string(jmethod)
            self.methods[name].append(method)
        
    def __getattr__(self, name):
        try:
            jfield = self.klass.getField(name)
        except:
            raise AttributeError("Could not find field %s" % name)
    
        STATIC = J.get_static_field("java/lang/reflect/Modifier", "STATIC", "I")
        if (J.call(jfield, "getModifiers", "()I") & STATIC) != STATIC:
            raise AttributeError("Field %s is not static" % name)
        klass = J.call(jfield, "getType", "()Ljava/lang/Class;")
        result = J.get_static_field(self.cname, name, sig(klass))
        if isinstance(result, J.JB_Object):
            result = JWrapper(result)
        return result
    
    def __setattr__(self, name, value):
        try:
            jfield = self.klass.getField(name)
        except:
            return object.__setattr__(self, name, value)

        STATIC = J.get_static_field("java/lang/reflect/Modifier", "STATIC", "I")
        if (J.call(jfield, "getModifiers", "()I") & STATIC) != STATIC:
            raise AttributeError()
        klass = J.call(jfield, "getType", "()Ljava/lang/Class;")
        result = J.set_static_field(self.cname, name, sig(klass), value)
    
    def __call_static(self, method_name, *args):
        '''Call the appropriate overloaded method with the given name
        
        :param method_name: the name of the method to call
        :param *args: the arguments to the method, which are used to
                      disambiguate between similarly named methods
        '''
        env = J.get_env()
        last_e = None
        for method in self.methods[method_name]:
            params = env.get_object_array_elements(method.getParameterTypes())
            is_var_args = J.call(method.o, "isVarArgs", "()Z")
            if len(args) < len(params) - (1 if is_var_args else 0):
                continue
            if len(args) > len(params) and not is_var_args:
                continue
            if is_var_args:
                pm1 = len(params)-1
                args1 = args[:pm1] + [args[pm1:]]
            else:
                args1 = args
            try:
                cargs = [cast(o, klass) for o, klass in zip(args1, params)]
            except:
                last_e = sys.exc_info()[1]
                continue
            rtype = J.call(method.o, "getReturnType", "()Ljava/lang/Class;")
            args_sig = "".join(map(sig, params))
            rsig = sig(rtype)
            msig = "(%s)%s" % (args_sig, rsig)
            result =  J.static_call(self.cname, method_name, msig, *cargs)
            if isinstance(result, J.JB_Object):
                result = JWrapper(result)
            return result
        raise TypeError("No matching method found for %s" % method_name)

    def __call__(self, *args):
        '''Constructors'''
        env = J.get_env()
        jconstructors = self.klass.getConstructors()
        for jconstructor in env.get_object_array_elements(jconstructors):
            constructor = J.get_constructor_wrapper(jconstructor)
            params = env.get_object_array_elements(
                constructor.getParameterTypes())
            is_var_args = J.call(constructor.o, "isVarArgs", "()Z")
            if len(args) < len(params) - (1 if is_var_args else 0):
                continue
            if len(args) > len(params) and not is_var_args:
                continue
            if is_var_args:
                pm1 = len(params)-1
                args1 = args[:pm1] + [args[pm1:]]
            else:
                args1 = args
            try:
                cargs = [cast(o, klass) for o, klass in zip(args1, params)]
            except:
                last_e = sys.exc_info()[1]
                continue
            args_sig = "".join(map(sig, params))
            msig = "(%s)V" % (args_sig)
            result =  J.make_instance(self.cname, msig, *cargs)
            result = JWrapper(result)
            return result
        raise TypeError("No matching constructor found")
    
def importClass(class_name, import_name = None):
    '''Import a wrapped class into the global context
    
    :param class_name: a dotted class name such as java.lang.String
    :param import_name: if defined, use this name instead of the class's name
    '''
    if import_name is None:
        if "." in class_name:
            import_name = class_name.rsplit(".", 1)[1]
        else:
            import_name = class_name
    frame = inspect.currentframe(1)
    frame.f_locals[import_name] = JClassWrapper(class_name)

def sig(klass):
    '''Return the JNI signature for a class'''
    name = J.call(klass, "getName", "()Ljava/lang/String;")
    if not (J.call(klass, "isPrimitive", "()Z") or 
            J.call(klass, "isArray", "()Z")):
        name = "L%s;" % name
    if name == 'void':
        return "V"
    if name == 'int':
        return "I"
    if name == 'byte':
        return "B"
    if name == 'boolean':
        return "Z"
    if name == 'long':
        return "J"
    if name == 'float':
        return "F"
    if name == 'double':
        return "D"
    if name == 'char':
        return "C"
    if name == 'short':
        return "S"
    return name.replace(".", "/")

def cast(o, klass):
    '''Cast the given object to the given class
    
    :param o: either a Python object or Java object to be cast
    :param klass: a java.lang.Class indicating the target class
    
    raises a TypeError if the object can't be cast.
    '''
    is_primitive = J.call(klass, "isPrimitive", "()Z")
    csig = sig(klass)
    if o is None:
        if not is_primitive:
            return None
        else:
            raise TypeError("Can't cast None to a primitive type")
        
    if isinstance(o, J.JB_Object):
        if J.call(klass, "isInstance", "(Ljava/lang/Object;)Z", o):
            return o
        classname = J.run_script("o.getClass().getCanonicalName()", dict(o=o))
        klassname = J.run_script("klass.getCanonicalName()", dict(klass=klass))
        raise TypeError("Object of class %s cannot be cast to %s",
                        classname, klassname)
    elif hasattr(o, "o"):
        return cast(o.o, klass)
    elif not np.isscalar(o):
        component_type = J.call(klass, "getComponentType", "()Ljava/lang/Class;")
        if component_type is None:
            raise TypeError("Argument must not be a sequence")
        if len(o) > 0:
            # Test if an element can be cast to the array type
            cast(o[0], component_type)
        return J.get_nice_arg(o, csig)
    elif is_primitive or csig in ('Ljava/lang/String;', 'Ljava/lang/Object;'):
        return J.get_nice_arg(o, csig)
    raise TypeError("Failed to convert argument to %s" % csig)
        
        

def do_execute(payload):
    '''Execute a Python command
    
    payload: first member is Python command string, second is local context
    '''
    logger.info("Executing script")
    try:
        command = J.to_string(payload[0])
        context = context_to_locals(payload[1])
        logger.debug("Script:\n%s" % command)
        exec(command, __builtins__.__dict__, context)
        logger.debug("Script evaluated")
        return J.run_script(
            """importPackage(Packages.org.scijava.plugins.scripting.cpython);
            var payload = new java.util.ArrayList();
            new CPythonScriptEngine.Message(
                CPythonScriptEngine.EngineCommands.EXECUTION, payload);
            """)
    except:
        logger.info("Exception caught during execute", exc_info=True)
        return J.run_script(
            """importPackage(Packages.org.scijava.plugins.scripting.cpython);
            var exception = new java.lang.RuntimeException(
            java.lang.String.format('Python exception: %s', e));
                var payload = new java.util.ArrayList();
                payload.add(exception);
                new CPythonScriptEngine.Message(
                    CPythonScriptEngine.EngineCommands.EXCEPTION, payload);
                """, dict(e=repr(sys.exc_info()[1])))

logger.info("Running scripting-cpython script")
thread = threading.Thread(target=engine_requester, name="Scripting-CPython Engine Requester")
thread.setDaemon(True)
thread.start()
