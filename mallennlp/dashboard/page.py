from logging import Logger
from typing import Any, Dict, List, Optional, Tuple, Callable, Iterable, Type, TypeVar

from dash.dependencies import Input, Output, State
import dash_core_components as dcc
import dash_html_components as html
from flask_login import current_user
from registrable import Registrable

from mallennlp.exceptions import NotPermittedError
from mallennlp.services.serde import serde, serialize, deserialize


T = TypeVar("T", bound="Page")


RegistrationHookType = Callable[
    [Type[T], str, List[Output], List[Input], List[State]], None
]
"""
A callable that accepts the following parameters:

PageClass : ``Type[T]``
    The class of the page.
method_name : ``str``
    The method name of the callback.
outputs : ``List[Output]``
    Outputs of the callback.
inputs : ``List[Input]``
    Inputs of the callback.
states : ``List[States]``
    States of the callback.
"""


PreHookType = Callable[[Type[T], str, str, Tuple[Any, ...]], None]
"""
A callable that accepts the following parameters:

PageClass : ``Type[T]``
    The class of the page.
method_name : ``str``
    The method name of the callback.
callback_id : ``str``
    A unique ID assigns to the invocation of the callback.
callback_args : ``Tuple[Any, ...]``
    The arguments of the callback invocation.
"""

PostHookType = Callable[[Type[T], str, str, Tuple[Any, ...], float, Any], None]
"""
A callable that accepts the following parameters:

PageClass : ``Type[T]``
    The class of the page.
method_name : ``str``
    The method name of the callback.
callback_id : ``str``
    A unique ID assigns to the invocation of the callback.
callback_args : ``Tuple[Any, ...]``
    The arguments of the callback invocation.
elapsed_time : ``float``
    The time (in seconds) it took the callback to execute.
retval : ``Any``
    The value returned by the callback.
"""

ErrHookType = Callable[[Type[T], str, str, Tuple[Any, ...], Exception], None]
"""
A callable that accepts the following parameters:

PageClass : ``Type[T]``
    The class of the page.
method_name : ``str``
    The method name of the callback.
callback_id : ``str``
    A unique ID assigns to the invocation of the callback.
callback_args : ``Tuple[Any, ...]``
    The arguments of the callback invocation.
error : ``Exception``
    The exception that was raised during the callback invocation.
"""

IgnoreHookType = Callable[[Type[T], str, str, Tuple[Any, ...]], None]
"""
A callable that accepts the following parameters:

PageClass : ``Type[T]``
    The class of the page.
method_name : ``str``
    The method name of the callback.
callback_id : ``str``
    A unique ID assigns to the invocation of the callback.
callback_args : ``Tuple[Any, ...]``
    The arguments of the callback invocation.
"""


def log_registration(
    PageClass: Type[T],
    method_name: str,
    outputs: List[Output],
    inputs: List[Input],
    states: List[State],
):
    PageClass.logger.debug(
        "callback %s.%s registered (%s, %s) -> %s",
        PageClass.__name__,
        method_name,
        inputs,
        states,
        outputs,
    )


DEFAULT_REGISTRATION_HOOKS: Tuple[RegistrationHookType, ...] = (log_registration,)


def log_received(
    PageClass: Type[T], method_name: str, callback_id: str, args: Tuple[Any, ...]
):
    PageClass.logger.debug(
        "callback %s.%s[%s] received", PageClass.__name__, method_name, callback_id
    )


def ensure_permissions(
    PageClass: Type[T], method_name: str, callback_id: str, args: Tuple[Any, ...]
):
    method = getattr(PageClass, method_name)
    permissions = getattr(method, "permissions")
    if permissions is not None and current_user.permissions < permissions:
        raise NotPermittedError(
            f"Callback {PageClass.__name__}.{method_name}[{callback_id}] "
            f"not permitted. You do not have adequate permissions"
        )


DEFAULT_PRE_HOOKS: Tuple[PreHookType, ...] = (log_received, ensure_permissions)


def log_success(
    PageClass: Type[T],
    method_name: str,
    callback_id: str,
    args: Tuple[Any, ...],
    elapsed_time: float,
    retval: Any,
):
    PageClass.logger.debug(
        "callback %s.%s[%s] succeeded in %.4f seconds",
        PageClass.__name__,
        method_name,
        callback_id,
        elapsed_time,
    )


DEFAULT_POST_HOOKS: Tuple[PostHookType, ...] = (log_success,)


def log_err(
    PageClass: Type[T],
    method_name: str,
    callback_id: str,
    args: Tuple[Any, ...],
    e: Exception,
):
    PageClass.logger.exception(e)
    PageClass.logger.error(
        "callback %s.%s[%s] failed", PageClass.__name__, method_name, callback_id
    )


DEFAULT_ERR_HOOKS: Tuple[ErrHookType, ...] = (log_err,)


def log_ignore(
    PageClass: Type[T], method_name: str, callback_id: str, args: Tuple[Any, ...]
):
    PageClass.logger.debug(
        "callback %s.%s[%s] ignored", PageClass.__name__, method_name, callback_id
    )


DEFAULT_IGNORE_HOOKS: Tuple[IgnoreHookType, ...] = (log_ignore,)


class Page(Registrable):
    permissions: int = 1
    """
    The minimum permissions level required to view the page. Defaults = 1 (any authenticated
    user).
    """

    navlink_name: Optional[str] = None
    """
    If set, this page will have a link in the navbar by this name.
    """

    route: str
    """
    The route the Page is registered under.
    """

    logger: Logger

    @serde
    class SessionState:
        """
        If the page needs to be stateful within a session, the state class should be defined here.
        The state instance will then be available as `self.s`.
        """

        pass

    @serde
    class Params:
        """
        If the page needs parameters from the URL they should be defined here.

        An instance of this class will then be passed to `Page.from_params` when
        initializing the page.
        """

        pass

    _store_name: str
    _callback_stores: List[str]
    _callback_error_divs: List[str]

    def __init__(self, state, params):
        self.s = state
        self.p = params

    def render(self) -> Tuple[html.Div, List[html.Div], List[Any]]:
        # Call this before `self.store()` in case `self.get_elements` modifies state.
        elements = self.get_elements()
        notifications = self.get_notifications()
        store = self.to_store()
        return (
            html.Div(
                [dcc.Store(id=self._store_name, data=store)]
                + [dcc.Store(id=s, data=store) for s in self._callback_stores]
                + elements
            ),
            [html.Div(id=e) for e in self._callback_error_divs],
            notifications,
        )

    def get_elements(self) -> List[Any]:
        raise NotImplementedError

    def get_notifications(self) -> List[Any]:
        return []

    @classmethod
    def from_params(cls, params):
        return cls(cls.SessionState(), params)

    @classmethod
    def from_store(cls, data: Dict[str, Any]):
        s = deserialize(cls.SessionState, data["s"])  # type: ignore
        p = deserialize(cls.Params, data["p"])  # type: ignore
        return cls(s, p)

    def to_store(self) -> Dict[str, Any]:
        return {"s": serialize(self.s), "p": serialize(self.p)}

    @classmethod
    def callback(
        cls: Type[T],
        outputs: List[Output] = None,
        inputs: List[Input] = None,
        states: List[State] = None,
        mutating: bool = True,
        registration_hooks: Iterable[RegistrationHookType] = DEFAULT_REGISTRATION_HOOKS,
        pre_hooks: Iterable[PreHookType] = DEFAULT_PRE_HOOKS,
        post_hooks: Iterable[PostHookType] = DEFAULT_POST_HOOKS,
        err_hooks: Iterable[ErrHookType] = DEFAULT_ERR_HOOKS,
        ignore_hooks: Iterable[IgnoreHookType] = DEFAULT_IGNORE_HOOKS,
        permissions: Optional[int] = None,
    ):
        """
        Register a Page callback.

        Parameters
        ----------
        outputs : ``List[Output]``, default = None
            A list (possibly empty) of outputs to update on the return of the callback.
            If given and non-empty, the number of outputs should equal the number of return
            values of the function.

        inputs : ``List[Input]``, default = None
            Input dependencies of the callback. The number of inputs + states is equal
            to the number of argument the callback should accept (ignore ``self`` or ``cls``).

        states : ``List[State]``, default = None
            State dependencies of the callback. The number of inputs + states is equal
            to the number of argument the callback should accept (ignore ``self`` or ``cls``).

        mutating : ``bool``, default = True
            Only relevant to an instance method callback. If ``True``, the ``Page``'s
            session state will be updated after the callback method returns.

        registration_hooks : ``Iterable[RegistrationHookType]``, default = DEFAULT_REGISTRATION_HOOKS
            Functions to run right when the callback is registered.

        pre_hooks : ``Iterable[PreHookType]``, default = DEFAULT_PRE_HOOKS
            Functions to run right before the callback executes.

        post_hooks : ``Iterable[PostHookType]``, default = DEFAULT_POST_HOOKS
            Functions to run right after the callback successfully executes.

        err_hooks : ``Iterable[ErrHookType]``, default = DEFAULT_ERR_HOOKS
            Functions to run after the callback fails.

        ignore_hooks : ``Iterable[IgnoreHookType]``, default = DEFAULT_IGNORE_HOOKS
            Functions to run when the callback raises ``PreventUpdate``.

        permissions : ``Optional[int]``, default = None
            Required permission level of the user in the active session in order
            to execute the callback.

        """
        if not outputs:
            outputs = []
        elif not isinstance(outputs, list):
            outputs = [outputs]
        inputs = inputs or []
        states = states or []

        def mark_callback(method):
            method.is_callback = True
            method.is_mutating = mutating
            method.callback_parameters = (outputs, inputs, states)
            method.registration_hooks = registration_hooks
            method.pre_hooks = pre_hooks
            method.post_hooks = post_hooks
            method.err_hooks = err_hooks
            method.ignore_hooks = ignore_hooks
            method.permissions = permissions
            return method

        return mark_callback
