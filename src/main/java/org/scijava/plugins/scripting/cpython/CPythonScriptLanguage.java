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
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.Reader;

import javax.script.ScriptEngine;

import org.scijava.log.LogService;
import org.scijava.plugin.Parameter;
import org.scijava.plugin.Plugin;
import org.scijava.script.AbstractScriptLanguage;
import org.scijava.script.ScriptLanguage;

/**
 * @author Lee Kamentsky
 *
 * A script language plugin for CPython and the Javabridge
 * 
 */
@Plugin(type = ScriptLanguage.class)
public class CPythonScriptLanguage extends AbstractScriptLanguage {
	private static final String PYTHON_SCRIPT = "scripting-cpython.py";
	@Parameter
	LogService logService;
	
	boolean initialized=false;
	
	@Override
	public ScriptEngine getScriptEngine() {
		synchronized(this) {
			if (! initialized) {
				final InputStream is = this.getClass().getClassLoader().getResourceAsStream(PYTHON_SCRIPT);
				final Reader rdr = new InputStreamReader(is);
				final StringBuffer sbScript = new StringBuffer();
				final char [] buffer = new char[65536];
				while (true) {
					try {
						final int nBytes = rdr.read(buffer);
						if (nBytes <= 0) break;
						sbScript.append(buffer, 0, nBytes);
					} catch (IOException e) {
						logService.warn(String.format(
								"Unexpected read failure in CPython script language for %s resource: %s",
								PYTHON_SCRIPT, e.getMessage()));
						return null;
					}
				}
				CPythonStartup.initializePythonThread(sbScript.toString());
				initialized=true;
			}
		}
		try {
			CPythonScriptEngine engine =  new CPythonScriptEngine();
			getContext().inject(engine);
			return engine;
			
		} catch (InterruptedException e) {
			logService.warn(e);
			return null;
		}
	}

	/* (non-Javadoc)
	 * @see imagej.script.AbstractScriptLanguage#getEngineName()
	 */
	@Override
	public String getEngineName() {
		return "cpython";
	}

	/* (non-Javadoc)
	 * @see imagej.script.AbstractScriptLanguage#getLanguageName()
	 */
	@Override
	public String getLanguageName() {
		return "CPython";
	}

	/* (non-Javadoc)
	 * @see java.lang.Object#finalize()
	 */
	@Override
	protected void finalize() throws Throwable {
		CPythonScriptEngine.closeService();
		super.finalize();
	}

}
