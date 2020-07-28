#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
    Dogma agent AI module - Dynamic Objective General Machine Agent

    dogma provides a unified framework for writing python programs that can
    load/unload during runtime (like plugins), but with each sub-program capable
    of loading and unloading plugins as well.


    from gevent import monkey
    monkey.patch_all()

    import dogma
    dog = dogma.Agent()
    dog.program_import('module.path')
    dog.init()

    Your program modules should be subclasses of the classes in the dogma.program
    module. If that program needs to be able to load and unload its own plugins, use
    the dogma.program.PlugableProgram class, and dogma.program.Plugin as your
    superclasses.


    MIT License

    Copyright (c) 2019 Fenris_Wolf, YSPStudios

    Permission is hereby granted, free of charge, to any person obtaining a copy
    of this software and associated documentation files (the "Software"), to deal
    in the Software without restriction, including without limitation the rights
    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
    copies of the Software, and to permit persons to whom the Software is
    furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in all
    copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
    SOFTWARE.

"""
import inspect
import importlib
import gevent
from six.moves import reload_module
from dogma.program import Program, PlugableProgram, ProgramLoadError


class Agent(object):
    """
    Agent class representing a dogma agent

    When subclassing and overriding the following methods, Agent.<method>()
    MUST be called as well in your override: __init__(), init(), check(),
    step()

    Attributes
    ----------
    programs : dict(str, Program)
        a dictionary of unique id's and loaded Program class objects.

    """
    programs = None

    def __init__(self):
        self.programs = {}


    def program_import(self, module, unique_id=None, classname="Program", config=None, plugins=None):
        """
        Registers a imports a program module, and loads its dogma.programs.Program subclass.

        Parameters
        ----------
        module : str
            string name of the module to import
        unique_id : Optional[str]
            unique id string to assign the program. by default the module name is used
        classname : Optional[str]
            string name of the module's class to instance. defaults to 'Program'
        config : Optional[object]
            abstract configuration object to be passed to the program instance.
        plugins : Optional[list(str)]
            list of plugins this program should load (if applicable)

        Returns
        ----------
        dogma.program.Program
            A subclass instance, the return value of Agent.program_load()

        Raises
        ----------
        dogma.program.ProgramLoadError

        """
        unique_id = unique_id or module
        mod = importlib.import_module(module)
        program = getattr(mod, classname)

        if not program:
            raise ProgramLoadError("Class %s for module %s not defined" % (classname, module))

        if not inspect.isclass(program):
            raise ProgramLoadError("Attribute %s for module %s is not a class" % (classname, module))

        if program == Program:
            raise ProgramLoadError("Class %s for module %s can not be dogma.program.Program" % (classname, module))

        return self.program_load(program, unique_id, config=config, plugins=plugins)



    def program_load(self, program, unique_id, config=None, state=None, plugins=None):
        """
        Instances a Program subclass object and calls its .load() method.
        Called automatically with Agent.program_new() after module import, and on program reload.

        Parameters
        ----------
        program : dogma.programs.Program
            a Program subclass to instance.
        unique_id : str
            unique id string to assign the program.
        config : Optional
            abstract configuration object to be passed to the program instance.
        state : Optional(dict)
            state dict to be passed to the program instance, used to restore a
            previous state. The return value from Program.unload() (or Agent.program_unload())
        plugins : Optional[list(str)]
            list of plugins this program should load (if applicable)

        Returns
        ----------
        dogma.program.Program
            A instance of the class specified in the `program` argument

        Raises
        ----------
        dogma.program.ProgramLoadError

        """
        if unique_id in self.programs:
            raise ProgramLoadError("Program already loaded: %s" % unique_id)

        if inspect.isclass(program):
            program = program(self)

        program.unique_id = unique_id
        self.programs[unique_id] = program
        program.load(config=config, state=state or {})

        if hasattr(program, 'plugin_import_list'):
            program.plugin_import_list(plugins)

        return program


    def program_unload(self, unique_id):
        """
        Unloads a Program instance and calls its .unload() method

        Parameters
        ----------
        unique_id : str
            unique id string of the program to unload.

        Returns
        ----------
        dogma.program.Program
            A instance of the class specified in the `program` argument

        Raises
        ----------
        dogma.program.ProgramLoadError

        """

        if unique_id is None or unique_id not in self.programs:
            raise ProgramLoadError("Cannot remove non-loaded program: %s" % unique_id)

        state = self.programs[unique_id].unload({})
        del self.programs[unique_id]
        return state


    def program_reload(self, unique_id, config=None):
        """
        Reloads a Program instance. This calls Agent.program_load(), reloads the base module for
        Program subclass, calls Agent.program_load(), and triggers the instance's .init() method.

        Parameters
        ----------
        unique_id : str
            unique id string of the program to unload.
        config : Optional
            abstract configuration object to be passed to the program instance.
            If None then the unloaded instance's config will be used.

        Raises
        ----------
        dogma.program.ProgramLoadError

        Returns
        ----------
        dogma.program.Program
            The new instance of the Program subclass

        """
        if unique_id is None or unique_id not in self.programs:
            raise ProgramLoadError("Cannot reload non-loaded program: %s" % unique_id)

        program = self.programs[unique_id]
        if config is None:
            config = program.config
        state = self.program_unload(unique_id)
        reload_module(inspect.getmodule(program))

        program = self.program_load(
            program.__class__,
            unique_id,
            config=config,
            state=state,
            plugins=config.get("plugins") # Note: this resets the plugin list. we should only reload active
            )
        program.init()
        return program


    def init(self):
        """
        Initializes all loaded Program subclass instances, calling each one's .init() method and
        waits until all greenlets are finished.
        """
        for program in self.programs.values():
            program.init()
        gevent.joinall([x.green for x in self.programs.values()])


    def shutdown(self):
        """
        Unloads all programs and plugins and ends the agents run loop
        """
        for program in [x for x in self.programs.keys()]:
            self.program_unload(program)


    def propogate(self, command, data):
        for program in self.programs:
            program.propogate(command, data)
