# dogma

Dynamic Objective General Machine Agent

dogma provides a unified framework for writing python programs that can
load/unload during runtime (like plugins), but with each sub-program capable
of loading and unloading plugins as well.

```python
from gevent import monkey
monkey.patch_all()

import dogma
dog = dogma.Agent()
dog.program_new('module.path', config_dict)
dog.init()
```

Your program modules should be subclasses of the classes in the dogma.program
module. If that program needs to be able to load and unload its own plugins, use
the dogma.program.PlugableProgram class, and dogma.program.Plugin as your
superclasses. (see program.py)
