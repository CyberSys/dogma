#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
    dogma.program - contains various program and plugin classes to be loaded by
    a dogma.Agent()

    Created on Mon Nov  5 18:03:20 2018

    @author: wolf

    These classes are meant to be superclasses as they do very little on their own
    (but yet, so much!). 3 classes are contained in this module:

    Program() - Basic program class, it runs in a seperate greenlet, so can use
        blocking code (within limits)

    PlugableProgram() - Similar to the Program class, but supports loading plugins
    in a format that mirrors the Agent/Program structure.


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
import importlib
import inspect
import gevent
from six.moves import reload_module

class ProgramLoadError(Exception):
    def __init__(self, value):
        self.parameter = value
    def __str__(self):
        return repr(self.parameter)


class Plugin(object):
    """Basic plugin class for the PlugableProgram class.
    """
    def __init__(self, parent):
        self.parent = parent
        #self.agent = parent.agent
        self.config = None

    def load(self, config=None, state=None):
        """Called when the plugin is loaded, this setups the local plugins config
        attribute. Your Plugin subclass should call this BEFORE executing any of
        its own code in this method. Note this should just contain initial setup
        code.
        """
        self.config = config

    def unload(self, state=None):
        """Called when the plugin is unloaded, or the program is unloaded/shutting
        down.
        """
        if state is None:
            state = {}
        return state

    def init(self):
        """Called when the program and plugins initialize. Plugins are initialized
        first, then the program.
        """
        pass

    def sibling(self, name):
        """
        Returns a sibling plugin: another plugin loaded by this program.
        """
        return self.parent.plugins.get(name)

    def uncle(self, name):
        """
        Returns a this plugins uncle: another program loaded by this program's agent.
        """
        return self.parent.agent.programs.get(name)

    def agent(self):
        """
        Returns the agent of this plugins parent program.
        """
        return self.parent.agent


class Program(object):
    """
        Class representing a Dogma Program.
    """
    def __init__(self, agent):
        self.agent = agent
        self.config = None
        self.green = None

    def load(self, config=None, state=None):
        """
        Called when the program is loaded (before initialization). Any setup
        code by your subclass should be in this method.
        """
        self.config = config

    def unload(self, state=None):
        """
        Called when the program unloads (or shutdown). This kills our running greenlet.
        """
        if state is None:
            state = {}
        if self.green and not self.green.dead:
            self.green.kill()
        return state

    def init(self):
        """
        Called when initializing the program. Your Program subclass needs to call
        Program.init() at the start (or end) of your subclass.init() method
        (your choice, but remember calling Program.init will spawn our run greenlet)
        """
        self.green = gevent.spawn(self.run)

    def run(self):
        """
        This method MUST be overwriten by your subclass or a NotImplementedError
        is raised. All code in this method is run in a sepeate greenlet.
        """
        raise NotImplementedError()



class PlugableProgram(Program):
    """
    Class representing a Dogma Program, capable of loading plugins. A subclass of
    dogma.programs.Program.
    """
    def __init__(self, agent):
        Program.__init__(self, agent)
        self.plugins = {}


    def load(self, config=None, state=None):
        """
        Identical to Program.load() but loads any plugins defined in the config.
        """
        Program.load(self, config, state)
        for plug in self.config.get('plugins', []):
            self.plugin_new(plug, self.config.get(plug, {}))


    def unload(self, state=None):
        """
        Unloads the PlugableProgram from the agent. Any plugins loaded by
        this program also have their unload() methods triggered. This also
        kills this PlugableProgram's greenlet
        """
        #state = Program.unload(self, state)
        if state is None:
            state = {}
        for plugin in self.plugins:
            state[plugin.name] = plugin.unload({})
            del self.plugins[plugin.name]
        if self.green and not self.green.dead:
            self.green.kill()
        return state


    def init(self):
        """
        Called when initializing the program. Your Program subclass needs to call
        PlugableProgram.init() at the start (or end) of your subclass.init() method.
        This calls Plugin.init() for any plugins loaded.
        (your choice, but remember calling PlugableProgram.init will spawn our run
         greenlet)
        """
        for plugin in self.plugins.values():
            plugin.init()
        Program.init(self)


    def run(self):
        """
        This method MUST be overwriten by your subclass or a NotImplementedError
        is raised. All code in this method is run in a sepeate greenlet.
        """
        Program.run(self)


    def plugin_new(self, path, config=None):
        """
        Adds and loads a plugin (or plugins), based on module path.
        """
        mod = importlib.import_module(path)
        loaded = False

        for entry in [getattr(mod, i) for i in dir(mod)]:
            if not inspect.isclass(entry):
                continue
            if issubclass(entry, Plugin) and entry != Plugin:
                loaded = True
                self.plugin_load(entry, config=config)

        if not loaded:
            raise ProgramLoadError("No Plugin subclass in %s" % path)


    def plugin_load(self, plugin, config=None, state=None):
        """
        Loads a plugin.
        """
        if inspect.isclass(plugin):
            plugin = plugin(self)

        name = plugin.__class__.__name__
        if name in self.plugins:
            raise ProgramLoadError("Program already loaded: %s" % name)

        self.plugins[name] = plugin
        plugin.load(config=config, state=state or {})


    def plugin_unload(self, plugin):
        """
        Unloads and removes a plugin.
        """
        name = plugin.__class__.__name__
        if name not in self.plugins:
            raise ProgramLoadError("Cannot remove non-existant plugin: %s" % name)

        state = self.plugins[name].unload({})
        del self.plugins[name]
        return state


    def plugin_reload(self, plugin):
        """
        Reloads a plugin.
        """
        name = plugin.__class__.__name__
        config = self.plugins[name].config
        state = self.plugin_unload(plugin)
        module = reload_module(inspect.getmodule(plugin))
        self.plugin_load(getattr(module, name), config, state)
