# -*- coding: utf-8 -*-

from __future__ import (absolute_import, division,
                        print_function)

from srttools.read_config import read_config
from astropy.time import Time
from astropy.coordinates import SkyCoord
import astropy.units as u
import pytest

from srttools.scan import Scan, HAS_MPL
from srttools.io import print_obs_info_fitszilla
from srttools.io import locations
import os
import numpy as np
import glob
import logging


@pytest.fixture()
def logger():
    logger = logging.getLogger('Some.Logger')
    logger.setLevel(logging.INFO)

    return logger


class Test1_Scan(object):
    @classmethod
    def setup_class(klass):
        import os

        klass.curdir = os.path.dirname(__file__)
        klass.datadir = os.path.join(klass.curdir, 'data')

        klass.fname = \
            os.path.abspath(
                os.path.join(klass.datadir, 'gauss_dec',
                             'Dec0.fits'))
        h5file = klass.fname.replace('.fits', '.hdf5')
        if os.path.exists(h5file):
            os.unlink(h5file)

        klass.config_file = \
            os.path.abspath(os.path.join(klass.datadir, 'test_config.ini'))

        read_config(klass.config_file)

    def test_print_info(self, capsys):
        print_obs_info_fitszilla(self.fname)
        out, err = capsys.readouterr()
        assert 'bandwidth' in out.lower()

    def test_repr(self):
        scan = Scan(self.fname)
        out = repr(scan)
        assert 'scan from file' in out.lower()

    def test_print(self, capsys):
        scan = Scan(self.fname)
        print(scan)
        out, err = capsys.readouterr()
        assert 'scan from file' not in out.lower()

    def test_scan(self):
        '''Test that data are read.'''

        scan = Scan(self.fname)
        scan.write('scan.hdf5', overwrite=True)
        scan2 = Scan('scan.hdf5')
        assert scan.meta == scan2.meta

    def test_scan_nofilt_executes(self):
        '''Test that data are read.'''

        scan = Scan(self.fname, nofilt=True)

    def test_scan_from_table(self):
        '''Test that data are read.'''
        from astropy.table import Table
        scan = Scan(self.fname)
        scan.write('scan.hdf5', overwrite=True)
        table = Table.read('scan.hdf5', path='scan')
        scan_from_table = Scan(table)
        for c in scan.columns:
            assert np.all(scan_from_table[c] == scan[c])
        for m in scan_from_table.meta.keys():
            assert scan_from_table.meta[m] == scan.meta[m]

    @pytest.mark.skipif('not HAS_MPL')
    def test_interactive(self):
        scan = Scan(self.fname)
        scan.interactive_filter('Ch0', test=True)

    @pytest.mark.parametrize('fname', ['med_data.fits',
                                       'srt_data_tp_multif.fits'])
    def test_coordinate_conversion_works(self, fname):
        scan = Scan(os.path.join(self.datadir, fname))
        obstimes = Time(scan['time'] * u.day, format='mjd', scale='utc')
        idx = 1 if '_multif' in fname else 0
        ref_coords = SkyCoord(ra=scan['ra'][:, idx],
                              dec=scan['dec'][:, idx],
                              obstime=obstimes,
                              location=locations[scan.meta['site']]
                              )
        altaz = ref_coords.altaz

        diff = np.abs(
             (altaz.az.to(u.rad) - scan['az'][:, idx]).to(u.arcsec).value)
        assert np.all(diff < 1)
        diff = np.abs(
            (altaz.alt.to(u.rad) - scan['el'][:, idx]).to(u.arcsec).value)
        assert np.all(diff < 1)

    @classmethod
    def teardown_class(klass):
        """Cleanup."""
        os.unlink('scan.hdf5')
        for f in glob.glob(os.path.join(klass.datadir, '*.hdf5')):
            os.unlink(f)


class Test2_Scan(object):
    @classmethod
    def setup_class(klass):

        klass.curdir = os.path.dirname(__file__)
        klass.datadir = os.path.join(klass.curdir, 'data')

        klass.fname = \
            os.path.abspath(
                os.path.join(klass.datadir, 'spectrum',
                             'roach_template.fits'))

        h5file = klass.fname.replace('.fits', '.hdf5')
        if os.path.exists(h5file):
            os.unlink(h5file)
        klass.config_file = \
            os.path.abspath(os.path.join(klass.datadir, 'spectrum.ini'))
        print(klass.config_file)

        read_config(klass.config_file)

    def test_scan(self):
        '''Test that data are read.'''

        scan = Scan(self.fname, debug=True)

        scan.write('scan.hdf5', overwrite=True)
        scan.baseline_subtract('rough', plot=True)

    def test_scan_baseline_unknown(self):
        '''Test that data are read.'''

        scan = Scan(self.fname, debug=True)

        scan.write('scan.hdf5', overwrite=True)
        with pytest.raises(ValueError):
            scan.baseline_subtract('asdfgh', plot=True)

    def test_scan_write_other_than_hdf5_raises(self):
        '''Test that data are read.'''

        scan = Scan(self.fname, debug=True)
        with pytest.raises(TypeError):
            scan.write('scan.fits', overwrite=True)
        with pytest.raises(TypeError):
            scan.write('scan.json', overwrite=True)
        with pytest.raises(TypeError):
            scan.write('scan.csv', overwrite=True)

    def test_scan_clean_and_splat(self):
        '''Test that data are read.'''

        scan = Scan(self.fname, debug=True)
        scan.meta['filtering_factor'] = 0.7
        with pytest.warns(UserWarning) as record:
            scan.clean_and_splat()
            assert np.any(
                ["Don't use filtering factors > 0.5" in r.message.args[0]
                 for r in record])

    @pytest.mark.parametrize('fname', ['srt_data.fits'])
    def test_coordinate_conversion_works(self, fname):
        scan = Scan(os.path.join(self.datadir, 'spectrum', fname), debug=True)
        obstimes = Time(scan['time'] * u.day, format='mjd', scale='utc')
        idx = 1 if '_multif' in fname else 0
        ref_coords = SkyCoord(ra=scan['ra'][:, idx],
                              dec=scan['dec'][:, idx],
                              obstime=obstimes,
                              location=locations[scan.meta['site']]
                              )
        altaz = ref_coords.altaz

        diff = np.abs(
            (altaz.az.to(u.rad) - scan['az'][:, idx]).to(u.arcsec).value)
        assert np.all(diff < 1)
        diff = np.abs(
            (altaz.alt.to(u.rad) - scan['el'][:, idx]).to(u.arcsec).value)
        assert np.all(diff < 1)

    @classmethod
    def teardown_class(klass):
        """Cleanup."""
        os.unlink('scan.hdf5')
        for f in glob.glob(os.path.join(klass.datadir, 'spectrum', '*.pdf')):
            os.unlink(f)
        for f in glob.glob(os.path.join(klass.datadir, 'spectrum', '*.hdf5')):
            os.unlink(f)
