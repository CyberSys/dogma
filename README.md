# Dogma

Dynamic Objective General Machine Agent

Dogma is a python framework for creating multi-level plugin applications.
It is designed to be a 'glue' framework, enabling easy IPC (Interprocess 
Communication) between individual python programs that use dogma, by removing 
the IP part from IPC and keeping them under a single process.


**Features:**
* **Multi-level plugin system**  
Seperate 'Programs' (top-level plugins) can load and unload sub-plugins.

* **Runtime Loading/Unloading**  
Programs and plugins can be loaded or unloaded during run, allowing applications 
using dogma to completely change tasks or purposes without ever restarting.

* **Minimal size and footprint.**  
The framework is small, and superclasses are desgined to be simple to work with.  
Each program and plugin is executed in is own greenlet using gevent to prevent 
blocking and threading mess.



```python
from gevent import monkey
monkey.patch_all()

import dogma
dog = dogma.Agent()
dog.program_import('module.path', 'unique_id', config_object)
dog.init()
```

Your program modules should be subclasses of the classes in the dogma.program
module. If that program needs to be able to load and unload its own plugins, use
the dogma.program.PlugableProgram class, and dogma.program.Plugin as your
superclasses. (see program.py)

