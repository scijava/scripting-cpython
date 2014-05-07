/*
 * #%L
 * SciJava Common shared library for SciJava software.
 * %%
 * Copyright (C) 2009 - 2014 Board of Regents of the University of
 * Wisconsin-Madison, Broad Institute of MIT and Harvard, and Max Planck
 * Institute of Molecular Cell Biology and Genetics.
 * %%
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions are met:
 * 
 * 1. Redistributions of source code must retain the above copyright notice,
 *    this list of conditions and the following disclaimer.
 * 2. Redistributions in binary form must reproduce the above copyright notice,
 *    this list of conditions and the following disclaimer in the documentation
 *    and/or other materials provided with the distribution.
 * 
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
 * AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
 * ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDERS OR CONTRIBUTORS BE
 * LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
 * CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
 * SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
 * INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
 * CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
 * ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
 * POSSIBILITY OF SUCH DAMAGE.
 * #L%
 */
package org.scijava.plugins.scripting.cpython;

import java.io.IOException;
import java.io.Reader;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.SynchronousQueue;

import javax.script.ScriptException;

import imagej.script.AbstractScriptEngine;


/**
 * @author Lee Kamentsky
 *
 * The script engine for CPython scripting via the javabridge.
 * 
 * The engine communicates with a Python thread via two static queues
 * which are used to arrange for the creation of an execution context
 * for the engine via two instance-specific queues.
 */
public class CPythonScriptEngine extends AbstractScriptEngine {

	public static final SynchronousQueue<Message> engineRequestQueue = new SynchronousQueue<Message>();
	public static final SynchronousQueue<Message> engineResponseQueue = new SynchronousQueue<Message>();
	
	private final SynchronousQueue<Message> requestQueue = new SynchronousQueue<Message>();
	private final SynchronousQueue<Message> responseQueue = new SynchronousQueue<Message>();
	
	/**
	 * @author Lee Kamentsky
	 * The commands that can be passed over the queues
	 */
	public static enum EngineCommands {
		/**
		 * Sent via the engineRequestQueue: create a new engine context 
		 */
		NEW_ENGINE,
		/**
		 * Sent via the requestQueue: execute a script
		 */
		EXECUTE,
		/**
		 * Send via the requestQueue: evaluate a script, returning
		 * a Java object representing the result.
		 * 
		 * The payload's first argument is a string to be executed.
		 * The payload's second argument is a Map<String, Object> that's
		 * used to populate the local context of the script evaluation.
		 */
		EVALUATE,
		/**
		 * Sent via the engineResponseQueue: the result of an NEW_ENGINE request
		 *
		 * The payload's first argument is a string to be executed.
		 * The payload's second argument is a Map<String, Object> that's
		 * used to populate the local context of the script evaluation.
		 */
		NEW_ENGINE_RESULT,
		/**
		 * Sent via the responseQueue: indicates successful script execution
		 */
		EXECUTION,
		/**
		 * Sent via the responseQueue: the result of an evaluation
		 * The payload contains the result
		 */
		EVALUATE_RESULT,
		/**
		 * Sent via the responseQueue: an exception occurred during execution or evaluation
		 * The payload contains a Java exception
		 */
		EXCEPTION,
		/**
		 * Sent via the requestQueue: close and destroy the Python side of the engine
		 * There is no response.
		 */
		CLOSE_ENGINE,
		/**
		 * Sent when closing the service
		 */
		CLOSE_SERVICE
		
	};
	public static class Message {
		final public EngineCommands command;
		final public List<Object> payload;
		public Message(EngineCommands command, List<Object> payload) {
			this.command = command;
			this.payload = payload;
		}
	}
	
	public CPythonScriptEngine() throws InterruptedException {
		engineRequestQueue.put(new Message(EngineCommands.NEW_ENGINE, Arrays.asList((Object)requestQueue, (Object)responseQueue)));
		engineResponseQueue.take();
	}
	/**
	 * Tell the Python side that the service is finished
	 * @throws InterruptedException
	 */
	static void closeService() throws InterruptedException {
		engineRequestQueue.put(new Message(EngineCommands.CLOSE_SERVICE, Collections.emptyList()));
	}
	@Override
	public Object eval(String script) throws ScriptException {
		Map<String, Object> context = new HashMap<String, Object>();
		// TODO: Populate context with current input bindings
		final Message request = new Message(EngineCommands.EVALUATE, Arrays.asList((Object)script, (Object)context));
		return eval(request);
	}
	/**
	 * @param request
	 * @return
	 * @throws ScriptException
	 */
	private Object eval(final Message request) throws ScriptException {
		try {
			requestQueue.put(request);
			Message result = responseQueue.take();
			if (result.command == EngineCommands.EXCEPTION) {
				if (result.payload.size() == 1) {
					Object oMessage = result.payload.get(0);
					if (oMessage instanceof String) {
						throw new ScriptException((String)oMessage);
					}
				}
				throw new ScriptException("Exception thrown but unknown format");
			}
			// TODO: Populate bindings with the context from the request's map
			return result.payload.get(0);
		} catch (InterruptedException e) {
			throw new ScriptException("Operation interrupted");
		}
	}

	@Override
	public Object eval(Reader reader) throws ScriptException {
		StringBuilder buf = new StringBuilder();
		char [] cbuf = new char [65536];
		while (true) {
			try {
				int nChars = reader.read(cbuf);
				if (nChars == 0) break;
				buf.append(cbuf, 0, nChars);
			} catch (IOException e) {
				throw new ScriptException(e);
			}
		}
		return eval(buf.toString());
	}

	/* (non-Javadoc)
	 * @see java.lang.Object#finalize()
	 */
	@Override
	protected void finalize() throws Throwable {
		requestQueue.put(new Message(EngineCommands.CLOSE_ENGINE, Collections.emptyList()));
		super.finalize();
	}

}
