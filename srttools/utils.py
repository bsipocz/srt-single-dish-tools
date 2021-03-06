"""
Random utilities
"""
import sys
import numpy as np
import warnings


DEFAULT_MPL_BACKEND = 'TKAgg'


try:
    import matplotlib

    # This is necessary. Random backends might respond incorrectly.
    matplotlib.use(DEFAULT_MPL_BACKEND)
    HAS_MPL = True
except ImportError:
    HAS_MPL = False

try:
    import statsmodels.api as sm
    version = [int(i) for i in sm.version.version.split('.')]

    # Minimum version 0.8.0
    if version < [0, 8, 0]:
        warnings.warn("Please update statsmodels")
        raise ImportError

    HAS_STATSM = True
except ImportError:
    HAS_STATSM = False


def _generic_dummy_decorator(*args, **kwargs):
    if len(args) == 1 and len(kwargs) == 0 and callable(args[0]):
        return args[0]
    else:
        def decorator(func):
            def decorated(*args, **kwargs):
                return func(*args, **kwargs)

            return decorated

        return decorator


try:
    from numba import jit, vectorize
except ImportError:
    warnings.warn("Numba not installed. Faking it")

    jit = vectorize = _generic_dummy_decorator


__all__ = ["mad", "standard_string", "standard_byte", "compare_strings",
           "tqdm", "jit", "vectorize"]


try:
    from tqdm import tqdm
except ImportError:
    def tqdm(x):
        return x


try:
    from statsmodels.robust import mad as mad  # pylint: disable=unused-import
except ImportError:
    def mad(data, c=0.6745, axis=None):
        """Straight from statsmodels's source code, adapted"""
        data = np.asarray(data)
        if axis is not None:
            center = np.apply_over_axes(np.median, data, axis)
        else:
            center = np.median(data)
        return np.median((np.fabs(data - center)) / c, axis=axis)


def standard_string(s):
    """Standard string representation for a given Python version

    Examples
    --------
    >>> standard_string(b'a')
    'a'
    >>> standard_string(None) is None
    True
    """
    if s is None:
        return None

    if sys.version_info >= (3, 0, 0):
        # for Python 3
        # This indexing should work for both lists of strings, and strings
        if hasattr(s, 'decode'):
            s = s.decode()  # or  s = str(s)[2:-1]
        # Try to see if it's a numpy array
        elif hasattr(s, 'dtype') and s.dtype.char == 'S':
            if s.size > 1:
                s = np.array(s, dtype='U')
    else:
        # for Python 2
        if isinstance(s[0], unicode):  # NOQA
            s = str(s)
        # Try to see if it's a numpy array
        elif hasattr(s, 'dtype') and s.dtype.char == 'U':
            if s.size > 1:
                s = np.array(s, dtype='S')
    return s


def standard_byte(s):
    """Standard byte representation for a given Python version

    Examples
    --------
    >>> standard_byte(b'a') == b'a'
    True
    >>> standard_byte(np.array([u'a'])[0]) == b'a'
    True
    """
    if hasattr(s, 'encode'):
        s = s.encode()
    elif hasattr(s, 'dtype') and s.dtype.char == 'U':
        if s.size > 1:
            s = np.array(s, dtype='S')
    return s


def compare_strings(s1, s2):
    """Compare strings, that might be bytes and unicode in some cases.

    Parameters
    ----------
    s1: string, byte or array of str/bytes
    s2 : string or byte

    Examples
    --------
    >>> compare_strings(b'a', 'a')
    True
    >>> compare_strings('a', u'a')
    True
    >>> import numpy as np
    >>> compare_strings(np.array(['a', 'b'], dtype='S'), u'a')
    array([ True, False], dtype=bool)
    """

    s1 = standard_string(s1)
    s2 = standard_string(s2)
    return s1 == s2
