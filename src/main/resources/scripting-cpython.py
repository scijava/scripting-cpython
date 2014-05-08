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
    try:
        command = J.to_string(payload[0])
        context = context_to_locals(payload[1])
        logger.debug("Script:\n%s" % command)
        result = eval(command, __builtins__.__dict__, context)
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
        return J.run_script(
            """importPackage(Packages.org.scijava.plugins.scripting.cpython);
            var exception = new java.lang.RuntimeException(
            java.lang.String.format('Python exception: %s', e));
                var payload = new java.util.ArrayList();
                payload.add(exception);
                new CPythonScriptEngine.Message(
                    CPythonScriptEngine.EngineCommands.EXCEPTION, payload);
                """, dict(e=repr(sys.exc_info()[1])))

def context_to_locals(context):
    '''convert the local context as a Java map to a dictionary of locals'''
    d = {}
    m = J.get_map_wrapper(context)
    for k in m:
        key = J.to_string(k)
        d[key] = m[k]
    return d

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
