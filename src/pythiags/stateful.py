#!/usr/bin/env python3
# obs.py

import enum
import threading
from abc import ABC
from abc import abstractmethod
from collections import defaultdict
from functools import partial
from functools import wraps
from random import randrange
from typing import Any
from typing import Callable
from typing import DefaultDict
from typing import Dict
from typing import List
from typing import Optional
from typing import Set
from typing import Tuple
from typing import Type
from typing import Union

from pythiags.background import run_later
from pythiags.utils import traced


class StateManager(ABC):
    """The Subject owns some important state and notifies observers when the
    state changes."""

    State: enum.EnumMeta = enum.Enum

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if (cls.State is enum.Enum) or (type(cls.State) is not enum.EnumMeta):
            raise NotImplementedError(
                f"{cls}.State mus be defined and be an enum"
            )

    StateTransition = Tuple[State, State]
    StateChangeTuple = Tuple["Observer", Optional[tuple], Optional[dict]]
    BlockingObservers = DefaultDict[
        Optional[StateTransition], Set[StateChangeTuple]
    ]
    BackgroundObservers = DefaultDict[
        Optional[StateTransition], Set[StateChangeTuple]
    ]

    def __init__(self, initial: State):
        self._state = initial
        self._blocking_observers: StateManager.BlockingObservers = defaultdict(
            set
        )
        self._background_observers: StateManager.BackgroundObservers = (
            defaultdict(set)
        )
        self.state_lock = threading.Lock()

    @property
    def observers(self):
        return {
            "blocking": self._blocking_observers,
            "background": self._background_observers,
        }

    def attach_blocking(
        self,
        observer: "Observer",
        transition: Optional[StateTransition] = None,
        cb_args: Optional[tuple] = None,
        cb_kwargs: Optional[dict] = None,
    ) -> None:
        self._blocking_observers[transition].add(
            (observer, cb_args or (), tuple((cb_kwargs or {}).items()))
        )

    def attach_background(
        self,
        observer: "Observer",
        transition: Optional[StateTransition] = None,
        cb_args: Optional[tuple] = None,
        cb_kwargs: Optional[dict] = None,
    ) -> None:
        self._background_observers[transition].add(
            (observer, cb_args or (), tuple((cb_kwargs or {}).items()))
        )

    def detach_blocking(self, observer: "Observer") -> None:
        self.__detach(observer, self._blocking_observers)
        # for transition, stored_observers in self._blocking_observers.items():
        #     for obs_arg_kwarg in stored_observers:
        #         if observer == obs_arg_kwarg[0]:
        #             self._blocking_observers[transition].remove(obs_arg_kwarg)
        #             return
        # raise KeyError(f"{observer} not in {self._blocking_observers}")

    def detach_background(self, observer: "Observer") -> None:
        self.__detach(observer, self._background_observers)
        # for transition, stored_observers in self._background_observers.items():
        #     for obs_arg_kwarg in stored_observers:
        #         if observer == obs_arg_kwarg[0]:
        #             self._background_observers[transition].remove(obs_arg_kwarg)
        #             return
        # raise KeyError(f"{observer} not in {self._background_observers}")

    def __detach(self, observer, observer_registry):
        for transition, stored_observers in observer_registry.items():
            for obs_arg_kwarg in stored_observers:
                if observer == obs_arg_kwarg[0]:
                    observer_registry[transition].remove(obs_arg_kwarg)
                    return
        raise KeyError(f"{observer} not in {observer_registry}")

    def __notify(
        self,
        observers_group,
        previous_state,
        current_state,
        background=False,
    ):
        current_transition = (previous_state, current_state)

        for transition, stored_observers in observers_group.items():
            if (not transition) or (transition == current_transition):
                for obs_arg_kwarg in stored_observers:
                    observer, args, kwargs = obs_arg_kwarg
                    try:
                        raw_cb = (
                            observer.on_state_change
                        )  # observer class, implements method
                    except AttributeError:
                        raw_cb = (
                            observer  # assume arbitrary callback registered
                        )

                    final_args = [
                        previous_state,
                        current_state,
                        *(args or ()),
                    ]
                    final_kwargs = kwargs or {}

                    if background:
                        run_later(raw_cb, 0, *final_args, **final_kwargs)
                    else:
                        raw_cb(*final_args, **final_kwargs)

    def notify(self, previous_state: State) -> None:
        """Trigger an update in each subscriber."""

        current_state = self.state
        current_transition = (previous_state, current_state)

        self.__notify(
            self._background_observers, *current_transition, background=True
        )
        self.__notify(self._blocking_observers, *current_transition)

        # for transition, stored_observers in self._background_observers.items():
        #     if (not transition) or (transition == current_transition):
        #         for obs_arg_kwarg in stored_observers:
        #             observer, args, kwargs = obs_arg_kwarg
        #             run_later(
        #                 observer.on_state_change,
        #                 0,
        #                 previous_state,
        #                 current_state,
        #                 *(args or ()),
        #                 **dict(kwargs or {}),
        #             )

        # for transition, stored_observers in self._blocking_observers.items():
        #     if (not transition) or (transition == current_transition):
        #         for obs_arg_kwarg in stored_observers:
        #             observer, args, kwargs = obs_arg_kwarg
        #             observer.on_state_change(
        #                 previous_state,
        #                 current_state,
        #                 *(args or ()),
        #                 **dict(kwargs or {}),
        #             )

    @property
    def state(self):
        return self._state

    @state.setter
    # @traced(print, log_time=True)
    def state(self, value):
        with self.state_lock:
            old = self._state
            self._state = value
        self.notify(old)

    def some_business_logic(self) -> None:
        """Usually, the subscription logic is only a fraction of what a Subject
        can really do.

        Subjects commonly hold some important business logic, that
        triggers a notification method whenever something important is
        about to happen (or after it).

        """

        print("\nSubject: I'm doing something important.\n")
        import random

        new = random.choice(list(self.State))
        self.state = new
        # print(f"Subject: My state has just changed to: {str(self.state)}")

    # endregion


class Observer(ABC):
    """The Observer interface declares the update method, used by subjects."""

    @abstractmethod
    def on_state_change(
        self, previous_state, current_state, *args, **kwargs
    ) -> None:
        """Receive update from subject."""
        pass


Observer = Union[
    ObserverClass,
    Callable[
        [
            enum.EnumMeta,  # previous_state
            enum.EnumMeta,  # current_state
            Optional[Tuple],  # args
            Optional[Dict],  # kwargs
        ],
        Any,
    ],
]


def toggles_state(state):
    """Decorate a method to toggle a state while its running."""

    def wrapper(func):
        @wraps(func)
        def wrapped(self, *a, **kw):
            try:
                self.state |= state
                ret = func(self, *a, **kw)
            finally:
                self.state &= ~state

            return ret

        return wrapped

    return wrapper
