import inspect
import traceback
import logging
from abc import ABCMeta, abstractmethod
from . import exceptions

log = logging.getLogger(__name__)

class Cog:
    def __init__(self, name):
        self.name = name
        self.commands = set()
        self.load()

    def __hash__(self):
        return hash(self.name)

    def __str__(self):
        return repr(self)[:-1] + " name: {0}>".format(self.name)

    def __eq__(self, other):
        return self.name == other.name

    def add_command(self, command):
        if(command in self.commands):
            self.commands.discard(command)
        self.commands.add(command)

    def delete_command(self, command):
        self.commands.discard(command)
    
    def load(self):
        self.loaded = True

    def unload(self):
        self.loaded = False

cogs = set()
commands = set()

# @TheerapakG: yea I know it's a hack, docstring aren't suppose to do this but I need it. Problems?
class ModifiabledocABCMeta(ABCMeta):
    def __new__(cls, clsname, bases, dct):

        for name, val in dct.copy().items():
            if name == 'doc':
                dct['__doc__'] = property(val, None, None, None)

        return super(ModifiabledocABCMeta, cls).__new__(cls, clsname, bases, dct)


class Command(metaclass = ModifiabledocABCMeta):
    def __init__(self, cog, name):
        self.name = name
        self.cog = cog
        self.alias = set()
        if Cog(cog) not in cogs:
            cogs.add(Cog(cog))
        for itcog in cogs:
            if itcog.name == cog:
                itcog.add_command(self)
        self.add_alias(name)
        commands.add(self)

    @abstractmethod
    def __call__(self, **kwargs):
        pass

    def __hash__(self):
        return hash(self.name)

    def __str__(self):
        return repr(self)[:-1] + " name: {0}>".format(self.name)

    def __eq__(self, other):
        return self.name == other.name
            
    def add_alias(self, alias):
        if alias in self.alias:
            log.warn("`{0}` is already an alias of command `{1}`".format(alias, self.name))
        else:
            self.alias.add(alias)

    def remove_alias(self, alias):
        try:
            self.alias.remove(alias)
        except KeyError:
            log.warn("`{0}` is not an alias of command `{1}`".format(alias, self.name))

    def remove_all_alias(self):
        self.alias = set([self.name])

# for the day we know there exist malformed function in module and we can get partial attr
# very hopeful dream right there
class UncallableCommand(Command):
    def __init__(self, cog, name):
        super().__init__(cog, name)

    def __call__(self, **kwargs):
        log.error("Command `{0}` in cog `{1}` is not callable.".format(self.name, self.cog))
        

class CallableCommand(Command):
    def __init__(self, cog, name, func):
        super().__init__(cog, name)
        self.func = func
    
    def doc(self):
        return "{}\n    alias: {}".format(self.func.__doc__, " ".join(self.alias))

    async def with_callback(self, cog, **kwargs):
        try:
            res = await self.func(**kwargs)
        except (exceptions.CommandError, exceptions.HelpfulError, exceptions.ExtractionError):
            # TODO: Check if this need unloading cogs 
            raise

        except exceptions.Signal:
            raise

        except Exception:   
            cog.unload()
            raise exceptions.CogError("unloaded cog `{0}`.".format(cog), expire_in= 40, traceback=traceback.format_exc()) from None
        return res

    def __call__(self, **kwargs):
        for itcog in cogs:
            if itcog.name == self.cog:
                if not itcog.loaded:
                    raise exceptions.CogError("Command `{0}` in cog `{1}` have been unloaded.".format(self.name, self.cog), expire_in=20)
                return self.with_callback(itcog, **kwargs)
        raise exceptions.CogError("Command `{0}` in cog `{1}` not found, very weird. Please try restarting the bot if this issue persist".format(self.name, self.cog), expire_in=20)

    def params(self):
        argspec = inspect.signature(self.func)
        return argspec.parameters.copy()

def command(cog, name, func):
    return CallableCommand(cog, name, func)

def getcmd(cmd):
    for command in commands:
        if cmd in command.alias:
            return command
    raise exceptions.CogError("command (or alias) `{0}` not found".format(cmd))

async def call(cmd, **kwargs):
    return await getcmd(cmd)(**kwargs)

def getcog(name):
    for itcog in cogs:
        if itcog.name == name:
            return itcog
    raise exceptions.CogError("cog `{0}` not found".format(name))