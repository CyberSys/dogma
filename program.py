#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
    dogma.program - contains various program and plugin classes to be loaded by
    a dogma.Agent()

    Created on Mon Nov  5 18:03:20 2018

    @author: Fenris_Wolf

    These classes are meant to be superclasses as they do very little on their own
    (but yet, so much!). 3 classes are contained in this module:

    Program() - Basic program class, it runs in a seperate greenlet, so can use
        blocking code (within limits)

    PlugableProgram() - Similar to the Program class, but supports loading plugins
    in a format that mirrors the Agent/Program structure.

    Plugin() - A plugin to be loaded by a PlugableProgram().

    PlugableProgram() and Plugin() follow the same structure as a dogma.Agent()
    and its programs. ie: there is not much difference coding a Plugin(), and
    coding a Program() (or PlugableProgram)

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
    """
    Basic plugin class for the PlugableProgram class, intended to be used as a superclass.

    Attributes
    ----------
    parent : dogma.program.Program
        The object instance of a Program subclass that this plugin is attached to.
    config : Object
        abstract configuration object placeholder.
    unique_id : str
        unique string identifier assigned to this plugin
    """
    config = None
    unique_id = None

    def __init__(self, parent):
        self.parent = parent


    def load(self, config=None, state=None):
        """
        Called when the plugin is loaded, this setups the local plugins config
        attribute. Your Plugin subclass should call this BEFORE executing any of
        its own code in this method. Note this should just contain initial setup
        code.

        Parameters
        ----------
        config : Optional
            abstract configuration object to be passed to the program instance.
        state : Optional(dict)
            state dict to be passed to the program instance, used to restore a
            previous state. The return value from Plugin.unload() (or
            PluggableProgram.plugin_unload())
        """
        self.config = config


    def unload(self, state=None):
        """
        Called when the plugin is unloaded, or the program is unloaded/shutting
        down.

        Parameters
        ----------
        """
        if state is None:
            state = {}
        return state


    def init(self):
        """
        Called when the program and plugins initialize. Plugins are initialized
        first, then the program.
        """
        pass


    def sibling(self, unique_id):
        """
        Returns a sibling plugin: another plugin loaded by this program.

        Parameters
        ----------
        unique_id: str
            string id of the sibling plugin

        Returns
        ----------
        dogma.program.Plugin | None
            A subclass instance

        """
        return self.parent.plugins.get(unique_id)


    def uncle(self, unique_id):
        """
        Returns a this plugins uncle: a sibling Program of this plugin's parent Program.

        Parameters
        ----------
        unique_id: str
            string id of the uncle program

        Returns
        ----------
        dogma.program.Program | None
            A subclass instance
        """
        return self.parent.agent.programs.get(unique_id)


    def agent(self):
        """
        Returns the agent of this plugins parent program.

        Returns
        ----------
        dogma.Agent
        """
        return self.parent.agent


    def propogate(self, command, data):
        pass


class Program(object):
    """
        Class representing a Dogma Program.
    """
    def __init__(self, agent):
        self.agent = agent
        self.config = None
        self.unique_id = None
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


    def propogate(self, command, data):
        pass


class PlugableProgram(Program):
    """
    Class representing a Dogma Program, capable of loading plugins. A subclass of
    dogma.programs.Program.
    """
    def __init__(self, agent):
        super().__init__(agent)
        self.plugins = {}


    def load(self, config=None, state=None):
        """
        Identical to Program.load() but loads any plugins defined in the config.
        """
        super().load(config, state)


    def unload(self, state=None):
        """
        Unloads the PlugableProgram from the agent. Any plugins loaded by
        this program also have their unload() methods triggered. This also
        kills this PlugableProgram's greenlet
        """
        if state is None:
            state = {}
        state['plugins'] = state.get('plugins', {})

        for name, plugin in self.plugins.items():
            state['plugins'][name] = plugin.unload({})

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
        super().init()


    def run(self):
        """
        This method MUST be overwriten by your subclass or a NotImplementedError
        is raised. All code in this method is run in a sepeate greenlet.
        """
        super().run()


    def plugin_import_list(self, plugins):
        if not plugins:
            return
        for kwargs in plugins:
            self.plugin_import(**kwargs)


    def plugin_import(self, module, unique_id=None, classname="Plugin", config=None):
        """
        Adds and loads a plugin (or plugins), based on module path
        """
        unique_id = unique_id or module
        mod = importlib.import_module(module)
        plugin = getattr(mod, classname)

        if not plugin:
            raise ProgramLoadError("Class %s for module %s not defined" % (classname, module))

        if not inspect.isclass(plugin):
            raise ProgramLoadError("Attribute %s for module %s is not a class" % (classname, module))

        if plugin == Plugin:
            raise ProgramLoadError("Class %s for module %s can not be dogma.program.Plugin" % (classname, module))

        return self.plugin_load(plugin, unique_id, config=config)


    def plugin_load(self, plugin, unique_id, config=None, state=None):
        """
        Loads a plugin.
        """
        if unique_id in self.plugins:
            raise ProgramLoadError("Plugin already loaded: %s" % unique_id)

        if inspect.isclass(plugin):
            plugin = plugin(self)

        plugin.unique_id = unique_id
        self.plugins[unique_id] = plugin
        plugin.load(config=config, state=state or {})
        return plugin


    def plugin_unload(self, unique_id):
        """
        Unloads and removes a plugin.
        """
        if unique_id is None or unique_id not in self.plugins:
            raise ProgramLoadError("Cannot remove non-loaded plugin: %s" % unique_id)

        state = self.plugins[unique_id].unload({})
        del self.plugins[unique_id]
        return state


    def plugin_reload(self, unique_id, config=None):
        """
        Reloads a plugin.
        """

        if unique_id is None or unique_id not in self.plugins:
            raise ProgramLoadError("Cannot reload non-loaded plugin: %s" % unique_id)

        plugin = self.plugins[unique_id]
        if config is None:
            config = plugin.config
        state = self.plugin_unload(unique_id)
        reload_module(inspect.getmodule(plugin))

        plugin = self.plugin_load(
            plugin.__class__,
            unique_id,
            config=config,
            state=state
            )

        plugin.init()
        return plugin


    def propogate(self, command, data):
        for plugin in self.plugins:
            plugin.propogate(command, data)
