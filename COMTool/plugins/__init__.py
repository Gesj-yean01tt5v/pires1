from . import dbg
from . import protocol
from .import terminal
# from . import myplugin

pluginClasses = [dbg.Plugin, protocol.Plugin, terminal.Plugin]
# pluginClasses.append(myplugin.Plugin)

builtinPlugins = {}
for c in pluginClasses:
    builtinPlugins[c.id] = c




