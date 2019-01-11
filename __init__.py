"""
    Dogma agent AI module - Dynamic Objective General Machine Agent

    dogma provides a unified framework for writing python programs that can
    load/unload during runtime (like plugins), but with each sub-program capable
    of loading and unloading plugins as well.

    from gevent import monkey
    monkey.patch_all()

    import dogma
    dog = dogma.Agent()
    dog.program_new('module.path', config_dict)
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
    """Agent class representing a AI
    When subclassing and overriding the following methods, Agent.<method>()
    MUST be called as well in your override: __init__(), init(), check(),
    step()"""
    def __init__(self):
        self.programs = {}


    def program_new(self, path, config=None):
        """
        """
        mod = importlib.import_module(path)
        throw = True

        for item in [getattr(mod, name) for name in dir(mod)]:
            if not inspect.isclass(item):
                continue
            if issubclass(item, Program) and not item in (Program, PlugableProgram):
                throw = False
                self.program_load(item, config=config)

        if throw:
            raise ProgramLoadError("No Program subclass in %s" % path)


    def program_load(self, program, config=None, state=None):
        """
        """
        if inspect.isclass(program):
            program = program(self)

        name = program.__class__.__name__
        if name in self.programs:
            raise ProgramLoadError("Program already loaded: %s" % name)

        self.programs[name] = program
        program.load(config=config, state=state or {})


    def program_unload(self, program):
        """
        """
        name = program.__class__.__name__
        if name not in self.programs:
            raise ProgramLoadError("Cannot remove non-existant program: %s" % name)

        state = self.programs[name].unload({})
        del self.programs[name]
        return state


    def program_reload(self, program):
        """
        """
        name = program.__class__.__name__
        config = self.programs[name].config
        state = self.program_unload(program)
        module = reload_module(inspect.getmodule(program))
        self.program_load(getattr(module, name), config, state)


    def init(self):
        """
        """
        for program in self.programs.values():
            program.init()
        gevent.joinall([x.green for x in self.programs.values()])
