import inspect
import logging
import typing
from abc import ABC
from typing import Dict, Any, Callable, TypeVar

from pydantic import BaseModel, create_model
from pydantic.fields import FieldInfo

from eidolon_sdk.cpu.agent_bus import CallContext
from eidolon_sdk.cpu.processing_unit import ProcessingUnit
from eidolon_sdk.reference_model import Specable
from eidolon_sdk.util.class_utils import get_function_details


# todo, llm function should require annotations and error if they are not present
def llm_function(fn):
    sig = inspect.signature(fn).parameters
    hints = typing.get_type_hints(fn, include_extras=True)
    fields = {}
    for param, hint in filter(lambda tu: tu[0] != 'return', hints.items()):
        if hasattr(hint, '__metadata__') and isinstance(hint.__metadata__[0], FieldInfo):
            field: FieldInfo = hint.__metadata__[0]
            field.default = sig[param].default
            fields[param] = (hint.__origin__, field)
        else:
            # _empty default isn't being handled by create_model properly (still optional when it should be required)
            default = ... if getattr(sig[param].default, "__name__", None) == '_empty' else sig[param].default
            fields[param] = (hint, default)

    function_name, clazz = get_function_details(fn)
    input_model = create_model(f'{clazz}_{function_name}InputModel', **fields)
    output_model = typing.get_type_hints(fn, include_extras=True).get('return', typing.Any)

    setattr(fn, 'llm_function', MethodInfo(
        name=function_name,
        description=fn.__doc__,
        input_model=input_model,
        output_model=output_model,
        fn=fn
    ))
    return fn


class MethodInfo(BaseModel):
    name: str
    description: str
    input_model: typing.Type[BaseModel]
    output_model: Any
    fn: Callable


class LogicUnitConfig(BaseModel):
    pass


T = TypeVar('T', bound=LogicUnitConfig)


class LogicUnit(ProcessingUnit, Specable[T], ABC):
    _tool_functions: Dict[str, MethodInfo]

    def __init__(self, spec: T = None, **kwargs):
        super().__init__(**kwargs)
        self.spec = spec
        self._tool_functions = self.discover()

    def discover(self):
        return {
            method_name: getattr(method, 'llm_function')
            for method_name in dir(self)
            for method in [getattr(self, method_name)]
            if hasattr(method, 'llm_function')
        }

    def is_sync(self):
        return True

    async def _execute(self, call_context: CallContext, method_info: MethodInfo, args: Dict[str, Any]) -> Dict[str, Any]:
        # if this is a sync tool call just call execute, if it is not we need to store the state of the conversation and call in memory
        if self.is_sync():
            converted_input = method_info.input_model.model_validate(args)
            logging.info("calling tool " + method_info.name + " with args " + str(converted_input))
            result = await method_info.fn(self, **dict(converted_input))
            # if result is a base model, call model_dump on it. If it is a string wrap it in an object with a "text" key
            if isinstance(result, BaseModel):
                result = result.model_dump()
            elif isinstance(result, str):
                result = {"text": result}
            elif result is None:
                result = {}
            return result
        else:
            # todo -- store the conversation and args in memory
            raise NotImplementedError("Async tools are not yet supported.")
