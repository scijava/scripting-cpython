'''scripting-cpython.py - Attach to Java CPython scripting

scripting-cpython is licensed under the BSD license.  See the
accompanying file LICENSE for details.

 Copyright (C) 2009 - 2014 Board of Regents of the University of
 Wisconsin-Madison, Broad Institute of MIT and Harvard, and Max Planck
 Institute of Molecular Cell Biology and Genetics.
 All rights reserved.

'''

import javabridge as J
import threading
import logging
logger = logging.getLogger(__name__)

def engine_requester():
    J.attach()
    while True:
        try:
            msg = J.run_script(
            """importPackage(Packages.org.scijava.plugins.scripting.cpython);
               CPythonScriptEngine.engineRequestQueue.take();""")
            payload = J.get_collection_wrapper(
                J.run_script("msg.payload", dict(msg=msg)))
            if J.run_script(
                """importPackage(Packages.org.scijava.plugins.scripting.cpython);
                msg.command==CPythonScriptEngine.EngineCommand.NEW_ENGINE;
                """, dict(msg=msg)):
                do_new_engine(payload)
            elif J.run_script(
                """importPackage(Packages.org.scijava.plugins.scripting.cpython);
                msg.command==CPythonScriptEngine.EngineCommand.CLOSE_SERVICE;
                """, dict(msg=msg)):
                break
            else:
                J.run_script(
                """importPackage(Packages.org.scijava.plugins.scripting.cpython);
                var exception = new java.lang.RuntimeException(
                    java.lang.String.format('Unknown command: %s', msg.command.toString()));
                var payload = new java.util.ArrayList();
                payload.add(exception);
                var response = new CPythonScriptEngine.Message(EngineCommand.EXCEPTION, payload);
                CPythonScriptEngine.engineResponseQueue.put(response);
                """)
                
        except e:
            # To do: how to handle failure, probably from .take()
            # Guessing that someone has managed to interrupt our thread
            logger.warn("Exiting script service thread: %s" % repr(e))
    J.detach()
            
def engine(q_request, q_response):
    J.attach()
    while True:
        try:
            msg = J.run_script(
            """importPackage(Packages.org.scijava.plugins.scripting.cpython);
               CPythonScriptEngine.engineRequestQueue.take();""")
            payload = J.get_collection_wrapper(
                J.run_script("msg.payload", dict(msg=msg)))
            if J.run_script(
                """importPackage(Packages.org.scijava.plugins.scripting.cpython);
                msg.command==CPythonScriptEngine.EngineCommand.EXECUTE;
                """, dict(msg=msg)):
                response = do_execute(payload)
            elif J.run_script(
                """importPackage(Packages.org.scijava.plugins.scripting.cpython);
                msg.command==CPythonScriptEngine.EngineCommand.EVALUATE;
                """, dict(msg=msg)):
                response = do_evaluate(payload)
            elif J.run_script(
                """importPackage(Packages.org.scijava.plugins.scripting.cpython);
                msg.command==CPythonScriptEngine.EngineCommand.CLOSE_ENGINE;
                """, dict(msg=msg)):
                break
            else:
                response = J.run_script(
                """importPackage(Packages.org.scijava.plugins.scripting.cpython);
                var exception = new java.lang.RuntimeException(
                    java.lang.String.format('Unknown command: %s', msg.command.toString()));
                var payload = new java.util.ArrayList();
                payload.add(exception);
                new CPythonScriptEngine.Message(EngineCommand.EXCEPTION, payload);
                """, dict(msg=msg))
            J.run_script("q_response.put(response);", 
                         dict(q_response=q_response,
                              response=response))
        except e:
            # To do: how to handle failure, probably from .take()
            # Guessing that someone has managed to interrupt our thread
            logger.warn("Exiting script engine thread", exc_info=True)
    J.detach()
    
def do_new_engine(payload):
    '''Create a new engine thread
    
    payload: first member is request queue, second is response queue
    '''
    thread = threading.Thread(target = engine, args=list(payload[:2]),
                              name = "Scripting-CPythonEngine")
    thread.setDaemon(True)
    thread.start()
    J.run_script(
    """importPackage(Packages.org.scijava.plugins.scripting.cpython);
    var payload = new java.util.ArrayList();
    var response = new CPythonScriptEngine.Message(EngineCommand.NEW_ENGINE_RESULT, payload);
    CPythonScriptEngine.engineResponseQueue.put(response);
    """)
    
def do_evaluate(payload):
    '''Evaluate a Python command
    
    payload: first member is Python command string, second is local context
    '''
    try:
        command = J.to_string(payload[0])
        context = dict(J.get_map_wrapper(payload[1]))
        result = eval(command, globals(), context)
        return J.run_script(
            """importPackage(Packages.org.scijava.plugins.scripting.cpython);
            var payload = new java.util.ArrayList();
            payload.add(result);
            new CPythonScriptEngine.Message(EngineCommand.EVALUATE_RESULT, payload);
            """, dict(result=result))
    except e:
        logger.info("Exception caught during eval", exc_info=True)
        return J.run_script(
            """importPackage(Packages.org.scijava.plugins.scripting.cpython);
            var exception = new java.lang.RuntimeException(
            java.lang.String.format('Python exception: %s', e));
                var payload = new java.util.ArrayList();
                payload.add(exception);
                new CPythonScriptEngine.Message(EngineCommand.EXCEPTION, payload);
                """, dict(msg=msg, e=repr(e)))

def do_execute(payload):
    '''Execute a Python command
    
    payload: first member is Python command string, second is local context
    '''
    try:
        command = J.to_string(payload[0])
        context = dict(J.get_map_wrapper(payload[1]))
        exec(command, globals(), context)
        return J.run_script(
            """importPackage(Packages.org.scijava.plugins.scripting.cpython);
            var payload = new java.util.ArrayList();
            new CPythonScriptEngine.Message(EngineCommand.EXECUTION, payload);
            """)
    except e:
        logger.info("Exception caught during execute", exc_info=True)
        return J.run_script(
            """importPackage(Packages.org.scijava.plugins.scripting.cpython);
            var exception = new java.lang.RuntimeException(
            java.lang.String.format('Python exception: %s', e));
                var payload = new java.util.ArrayList();
                payload.add(exception);
                new CPythonScriptEngine.Message(EngineCommand.EXCEPTION, payload);
                """, dict(msg=msg, e=repr(e)))

thread = threading.Thread(target=engine_requester, name="Scripting-CPython Engine Requester")
thread.setDaemon(True)
thread.start()
