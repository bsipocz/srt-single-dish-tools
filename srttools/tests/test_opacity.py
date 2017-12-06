from srttools.opacity import calculate_opacity, main_opacity
import numpy as np
import os

class TestOpacity(object):
    @classmethod
    def setup_class(klass):
        import os

        klass.curdir = os.path.dirname(__file__)
        klass.datadir = os.path.join(klass.curdir, 'data')

        klass.fname = \
            os.path.abspath(
                os.path.join(klass.datadir, 'gauss_skydip', 'skydip.fits'))

    def test_opacity(self):
        res = calculate_opacity(self.fname)
        vals = [res[k] for k in res.keys()]

        assert np.allclose(vals, 0.055, atol=0.005)

    def test_script(self):
        main_opacity([self.fname])
        assert os.path.exists(self.fname.replace('.fits', '_fit_Ch0.png'))
