#!/usr/bin/env python
"""Core classes"""
import collections
import copy
import inspect
import six

from .exceptions import PescadorError


class Streamer(object):
    '''A wrapper class for recycling iterables and generator functions, i.e.
    streamers.

    Wrapping streamers within an object provides
    two useful features:

    1. Streamer objects can be serialized (as long as its streamer can be)
    2. Streamer objects can instantiate a generator multiple times.

    The first feature is important for parallelization (see `zmq_stream`),
    while the second feature facilitates infinite streaming from finite data
    (i.e., oversampling).


    Attributes
    ----------
    streamer : generator or iterable
        Any generator function or iterable python object.

    args : list
    kwargs : dict
        Parameters provided to `streamer`, if callable.

    Examples
    --------
    Generate random 3-dimensional vectors

    >>> def my_generator(n):
    ...     for i in range(n):
    ...         yield i
    >>> stream = Streamer(my_generator, 5)
    >>> for i in stream:
    ...     print(i)  # Displays 0, 1, 2, 3, 4


    Or with a maximum number of items

    >>> for i in stream(max_items=3):
    ...     print(i)  # Displays 0, 1, 2


    Or infinitely many examples, restarting the generator as needed

    >>> for i in stream.cycle():
    ...     print(i)  # Displays 0, 1, 2, 3, 4, 0, 1, 2, ...


    An alternate interface for the same:

    >>> for i in stream(cycle=True):
    ...     print(i)  # Displays 0, 1, 2, 3, 4, 0, 1, 2, ...

    '''

    def __init__(self, streamer, *args, **kwargs):
        '''Initializer

        Parameters
        ----------
        streamer : iterable or generator function
            Any generator function or object that is iterable when
            instantiated.

        args, kwargs
            Additional positional arguments or keyword arguments passed to
            ``streamer()`` if it is callable.

        Raises
        ------
        PescadorError
            If ``streamer`` is not a generator or an Iterable object.

        '''

        if not (inspect.isgeneratorfunction(streamer) or
                isinstance(streamer, (collections.Iterable, Streamer))):
            raise PescadorError('`streamer` must be an iterable or callable '
                                'function that returns an iterable object.')

        self.streamer = streamer
        self.args = args
        self.kwargs = kwargs
        self.stream_ = None

    def copy(self):
        return copy.deepcopy(self)

    def __enter__(self, *args, **kwargs):
        streamer_copy = self.copy()
        streamer_copy._activate()
        return streamer_copy

    def __exit__(self, *exc):
        self._deactivate()
        return False

    @property
    def active(self):
        """Returns true if the stream is active
        (ie a StopIteration) has not been thrown.
        """
        return self.stream_ is not None

    def _activate(self):
        """Activates the stream."""
        if six.callable(self.streamer):
            # If it's a function, create the stream.
            self.stream_ = self.streamer(*(self.args), **(self.kwargs))

        else:
            # If it's iterable, use it directly.
            self.stream_ = iter(self.streamer)

    def _deactivate(self):
        self.stream_ = None

    def iterate(self, max_iter=None):
        '''Instantiate an iterator.

        Parameters
        ----------
        max_iter : None or int > 0
            Maximum number of iterations to yield.
            If ``None``, exhaust the stream.

        Yields
        ------
        obj : Objects yielded by the streamer provided on init.

        See Also
        --------
        cycle : force an infinite stream.

        '''
        # Use self as context manager / calls __enter__() => _activate()
        with self as active_streamer:
            for n, obj in enumerate(active_streamer.stream_):
                if max_iter is not None and n >= max_iter:
                    break
                yield obj

    def cycle(self):
        '''Iterate from the streamer infinitely.

        This function will force an infinite stream, restarting
        the streamer even if a StopIteration is raised.

        Yields
        ------
        obj : Objects yielded by the streamer provided on init.
        '''

        while True:
            for obj in self:
                yield obj

    def __call__(self, max_iter=None, cycle=False):
        '''Convenience interface for interacting with the Streamer.

        Parameters
        ----------
        max_iter : None or int > 0
            Maximum number of iterations to yield.
            If `None`, attempt to exhaust the stream.
            For finite streams, call iterate again, or use `cycle=True` to
            force an infinite stream.

        cycle: bool
            If `True`, cycle indefinitely.

        Yields
        ------
        obj : Objects yielded by the generator provided on init.

        See Also
        --------
        iterate
        cycle
        '''
        if cycle:
            gen = self.cycle()
        else:
            gen = self.iterate(max_iter=max_iter)

        for obj in gen:
            yield obj

    def __iter__(self):
        return self.iterate()
