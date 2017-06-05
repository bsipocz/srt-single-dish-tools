from .scan import Scan, list_scans
from .read_config import read_config, sample_config_file
from .fit import fit_baseline_plus_bell

import os
import sys
import warnings
import matplotlib.pyplot as plt
from .calibration import _get_calibrator_flux

try:
    import cPickle as pickle
except:
    import pickle

import numpy as np
from astropy.table import Table, vstack

CALIBRATOR_CONFIG = None

calist = ['3C147', '3C48', '3C123', '3C295', '3C286', 'NGC7027']
colors = ['k', 'b', 'r', 'g', 'c', 'm']
colors = dict(zip(calist, colors))


def decide_symbol(values):
    """Decide symbols for plotting.

    Assigns different symbols to RA scans, Dec scans, backward and forward.
    """
    raplus = values == "RA>"
    ramin = values == "RA<"
    decplus = values == "Dec>"
    decmin = values == "Dec<"
    symbols = np.array(['a' for i in values])
    symbols[raplus] = u"+"
    symbols[ramin] = u"s"
    symbols[decplus] = u"^"
    symbols[decmin] = u"v"
    return symbols


def get_fluxes(basedir, scandir, channel='Ch0', feed=0, plotall=False,
               debug=True, freqsplat=None):
    """Get fluxes from all scans in path."""
    # dname = os.path.basename(scandir)
    scan_list = \
        list_scans(basedir, [scandir])

    scan_list.sort()
    output_table = Table(names=["Dir", "File", "Scan Type", "Source", "Time",
                                "Frequency", "Bandwidth",
                                "Counts", "Counts Err",
                                "Width",
                                "Flux Density", "Flux Density Err",
                                "Kind",
                                "Elevation",
                                "Flux/Counts", "Flux/Counts Err",
                                "RA", "Dec",
                                "Fit RA", "Fit Dec"],
                         dtype=['U200', 'U200', 'U200', 'U200', np.longdouble,
                                np.float, np.float,
                                np.float, np.float,
                                np.float,
                                np.float, np.float,
                                "U200",
                                np.float,
                                np.float, np.float,
                                np.float, np.float,
                                np.float, np.float])

    if plotall:
        figures = []
        plotted_kinds = []

    nscan = len(scan_list)

    for i_s, s in enumerate(scan_list):
        print('{}/{}: Loading {}'.format(i_s + 1, nscan, s))
        sname = os.path.basename(s)
        try:
            # For now, use nosave. HDF5 doesn't store meta, essential for this
            scan = Scan(s, norefilt=True, nosave=True, debug=debug,
                        freqsplat=freqsplat)
        except:
            warnings.warn('{} is an invalid file'.format(s))
            continue
        ras = np.degrees(scan['ra'][:, feed])
        decs = np.degrees(scan['dec'][:, feed])
        time = np.mean(scan['time'][:])
        el = np.degrees(np.mean(scan['el'][:, feed]))
        source = scan.meta['SOURCE']
        backend = scan.meta['backend']
        pnt_ra = np.degrees(scan.meta['RA'])
        pnt_dec = np.degrees(scan.meta['Dec'])

        frequency = scan[channel].meta['frequency']

        bandwidth = scan[channel].meta['bandwidth']

        # Note: Formulas are in GHz here.
        flux, eflux = \
            _get_calibrator_flux(source, frequency / 1000,
                                 bandwidth / 1000, time=time)

        if flux is None:
            flux_density = 1 / bandwidth
            flux_density_err = 0
            flux = 1.
            eflux = 0
            kind = "Source"
        else:
            flux *= 1000
            eflux *= 1000
            # Config gives flux density (... Hz^-1). Normalize by bandwidth
            flux_density = flux / bandwidth
            flux_density_err = eflux / bandwidth
            kind = "Calibrator"

        y = scan[channel]

        ravar = np.max(ras) - np.min(ras)
        decvar = np.max(decs) - np.min(decs)
        if ravar > decvar:
            x = ras
            xvariab = 'RA'
        else:
            x = decs
            xvariab = 'Dec'

        if x[-1] > x[0]:
            scan_direction = '>'
        else:
            scan_direction = '<'
        scan_type = xvariab + scan_direction

        model, fit_info = fit_baseline_plus_bell(x, y, kind='gauss')

        try:
            uncert = fit_info['param_cov'].diagonal() ** 0.5
        except:
            warnings.warn("Fit failed in scan {s}".format(s=s))
            continue

        baseline = model['Baseline']
        bell = model['Bell']
        # pars = model.parameters
        pnames = model.param_names
        counts = model.amplitude_1.value
        if xvariab == "RA":
            fit_ra = bell.mean
            fit_width = bell.stddev * np.cos(np.radians(pnt_dec))
            fit_dec = None
            to_plot = pnt_ra
        elif xvariab == "Dec":
            fit_ra = None
            fit_dec = bell.mean
            to_plot = pnt_dec
            fit_width = bell.stddev

        index = pnames.index("amplitude_1")

        counts_err = uncert[index]

        if plotall:
            figure_name = '{}_{}_{}'.format(source, xvariab, backend)
            first = False
            if figure_name not in figures:
                first = True
                figures.append(figure_name)
                plotted_kinds.append(kind)

            plt.figure(figure_name)

            if first:
                plt.axvline(to_plot)
            data = plt.plot(x, np.array(y - baseline(x)),
                            label='{:.2f}'.format(el))
            plt.plot(x, bell(x), color=plt.getp(data[0], 'color'))
            plt.title('{} (baseline-subtracted)'.format(source))
            plt.xlabel(xvariab)

        flux_over_counts = flux / counts
        flux_over_counts_err = \
            (counts_err / counts + eflux / flux) * flux_over_counts

        output_table.add_row([scandir, sname, scan_type, source, time,
                              frequency, bandwidth, counts, counts_err,
                              fit_width,
                              flux_density, flux_density_err, kind, el,
                              flux_over_counts, flux_over_counts_err,
                              pnt_ra, pnt_dec, fit_ra, fit_dec])

    if plotall:
        for i_f, f in enumerate(figures):
            fig = plt.figure(f)
            if plotted_kinds[i_f] == 'Calibrator':
                plt.legend()
            fig.savefig(f + ".png")

    return output_table


def get_full_table(config_file, channel='Ch0', feed=0, plotall=False,
                   picklefile=None, debug=True, freqsplat=None):
    """Get all fluxes in the directories specified by the config file."""
    config = read_config(config_file)

    dir_list = config['list_of_directories']
    tables = {}

    ndir = len(dir_list)
    for i_d, d in enumerate(dir_list):
        print('\n-----------------\n')
        print('{}/{}: Loading data in {}'.format(i_d + 1, ndir, d))
        print('\n-----------------\n')

        output_table = get_fluxes(config['datadir'], d, channel=channel,
                                  feed=feed, plotall=plotall, debug=debug,
                                  freqsplat=freqsplat)
        tables[d] = output_table

    full_table = Table(vstack(list(tables.values())))
    if picklefile is not None:
        with open(picklefile, 'wb') as f:
            pickle.dump(full_table, f)
    return full_table


def show_calibration(full_table, feed=0, plotall=False):
    """Show the results of calibration."""
    import matplotlib as mpl

    dir_list = list(set(full_table["Dir"]))

    calibrator_table = full_table[full_table["Kind"] == "Calibrator"]

    source_table = full_table[full_table["Kind"] == "Source"]

    for d in dir_list:
        subtable = calibrator_table[calibrator_table["Dir"] == d]
        if len(subtable) == 0:
            continue

        symbols = decide_symbol(subtable["Scan Type"])
        for k in colors.keys():
            if k in subtable["Source"][0]:
                source_color = colors[k]
                break
        else:
            source_color = 'grey'

        # ----------------------- Pointing vs. ELEVATION -------------------
        plt.figure("Pointing Error vs Elevation")
        good_ra = subtable["Fit RA"] == subtable["Fit RA"]
        good_dec = subtable["Fit Dec"] == subtable["Fit Dec"]

        ra_pnt = subtable["RA"]
        dec_pnt = subtable["Dec"]
        ra_fit = subtable["Fit RA"]
        dec_fit = subtable["Fit Dec"]

        el = subtable["Elevation"]
        ra_err = (ra_fit - ra_pnt) / np.cos(np.radians(dec_pnt))
        dec_err = dec_fit - dec_pnt
        pointing_err = np.sqrt(np.mean(ra_err[good_ra])**2 +
                               np.mean(dec_err[good_dec])**2)

        plt.scatter(np.mean(el), pointing_err * 60, color='k', marker='o')
        for _e, _r, _d,  _s in zip(el, ra_err, dec_err, symbols):
            plt.scatter(_e, _r * 60, color='r', marker=_s)
            plt.scatter(_e, _d * 60, color='b', marker=_s)

        fc = np.mean(subtable["Flux/Counts"]) / subtable["Bandwidth"][0]
        fce = np.sqrt(
            np.sum(subtable["Flux/Counts Err"] ** 2)) / \
            len(subtable) / subtable["Bandwidth"][0]
        fce = np.max([fce, np.std(fc)])

        # ----------------------- Calibration vs. ELEVATION -------------------
        plt.figure("Vs Elevation")
        plt.errorbar(np.mean(subtable["Elevation"]), fc, yerr=fce,
                     ecolor=source_color,
                     elinewidth=3)

        # ----------------------- Width vs. ELEVATION -------------------
        ras = np.char.rstrip(subtable["Scan Type"], "><") == "RA"
        decs = np.char.rstrip(subtable["Scan Type"], "><") == "Dec"

        plt.figure("Width Vs Elevation")
        plt.scatter(subtable["Elevation"][ras], subtable["Width"][ras],
                    color=source_color, marker='o')
        plt.scatter(subtable["Elevation"][decs], subtable["Width"][decs],
                    color=source_color, marker='^')

    plt.figure("Vs Elevation")
    plt.ylabel("Jansky / Counts")
    plt.xlabel("Elevation")

    plt.figure("Width Vs Elevation")
    plt.xlabel("Elevation")
    plt.ylabel("Gaussian Width (deg)")

    plt.figure("Pointing Error vs Elevation")
    plt.title("Pointing Error vs Elevation (black: total; red: RA; blue: Dec)")
    plt.xlabel('Elevation')
    plt.ylabel('Pointing error (arcmin)')

    rap_symb = mpl.lines.Line2D([0], [0], linestyle="none", c='r', marker='+')
    dep_symb = mpl.lines.Line2D([0], [0], linestyle="none", c='b', marker='^')
    ram_symb = mpl.lines.Line2D([0], [0], linestyle="none", c='r', marker='s')
    dem_symb = mpl.lines.Line2D([0], [0], linestyle="none", c='b', marker='v')
    tot_symb = mpl.lines.Line2D([0], [0], linestyle="none", c='k', marker='o')

    plt.legend([rap_symb, dep_symb, ram_symb, dem_symb, tot_symb],
               ['RA>', 'Dec>', 'RA<', 'Dec<', 'Tot'], numpoints=1)

    f_c_ratio = calibrator_table["Flux/Counts"]

    good = (f_c_ratio == f_c_ratio) & (f_c_ratio > 0)
    fc = np.mean(f_c_ratio[good])
    f_c_ratio_err = calibrator_table["Flux/Counts Err"]
    good = (f_c_ratio_err == f_c_ratio_err) & (f_c_ratio_err > 0)
    fce = np.sqrt(np.sum(f_c_ratio_err[good] ** 2))\
        / len(calibrator_table)

    source_table["Flux Density"] = \
        source_table["Counts"] * fc / source_table["Bandwidth"]
    source_table["Flux Density Err"] = \
        (source_table["Counts Err"] / source_table["Counts"]) * \
        source_table["Flux Density"]
    source_table["Flux Density Systematic"] = \
        fce / fc * source_table["Flux Density"]

    sources = list(set(source_table["Source"]))
    source_colors = ['k', 'b', 'r', 'g', 'c', 'm']
    for i_s, s in enumerate(sources):
        c = source_colors[i_s % len(sources)]
        filtered = source_table[source_table["Source"] == s]

        if len(filtered) > 20:
            plt.figure(s)
            from astropy.visualization import hist
            hist(filtered["Flux Density"], bins='knuth',
                 histtype='stepfilled')

            plt.xlabel("Flux values")
        plt.figure(s + '_callc')
        plt.errorbar(filtered['Time'], filtered['Flux Density'],
                     yerr=filtered['Flux Density Err'], label=s, fmt=None,
                     ecolor=c, color=c)
        plt.fill_between(
            filtered['Time'],
            filtered['Flux Density'] - filtered['Flux Density Systematic'],
            filtered['Flux Density'] + filtered['Flux Density Systematic'],
            color=c, alpha=0.1,
            label=s + '-systematic')

        plt.legend()
        plt.xlabel('Time (MJD)')
        plt.ylabel('Flux (Jy)')
        plt.savefig(s + '_callc.png')
        np.savetxt(s + '_callc_data.txt',
                   np.array([filtered['Time'],
                             filtered['Flux Density'],
                             filtered['Flux Density Err']]).T)

        plt.figure(s + '_lc')
        plt.errorbar(filtered['Time'], filtered['Counts'],
                     yerr=filtered['Counts Err'], label=s, fmt=None)

        plt.xlabel('Time (MJD)')
        plt.ylabel('Counts')
        plt.savefig(s + '_lc.png')
        np.savetxt(s + '_lc_data.txt',
                   np.array([filtered['Time'],
                             filtered['Counts'],
                             filtered['Counts Err']]).T)

        plt.legend()
    plt.show()


def test_calibration_tp():
    """Test that the calibration executes completely."""
    import pickle
    curdir = os.path.abspath(os.path.dirname(__file__))
    config_file = \
        os.path.abspath(os.path.join(curdir, '..', '..',
                                     'TEST_DATASET',
                                     'test_calib.ini'))
    full_table = get_full_table(config_file, plotall=True,
                                picklefile='data_tp.pickle')

    with open('data_tp.pickle', 'rb') as f:
        full_table = pickle.load(f)
    show_calibration(full_table)


def test_calibration_roach():
    """Test that the calibration executes completely, ROACH version."""
    curdir = os.path.abspath(os.path.dirname(__file__))
    config_file = \
        os.path.abspath(os.path.join(curdir, '..', '..',
                                     'TEST_DATASET',
                                     'test_calib_roach.ini'))
    get_full_table(config_file, plotall=True,
                   picklefile='data_r2.pickle')

    with open('data_r2.pickle', 'rb') as f:
        full_table = pickle.load(f)
    show_calibration(full_table)


def main(args=None):
    """Main function."""
    import argparse
    import os

    description = ('Load a series of scans from a config file '
                   'and produce a map.')
    parser = argparse.ArgumentParser(description=description)

    parser.add_argument("--sample-config", action='store_true', default=False,
                        help='Produce sample config file')

    parser.add_argument("-c", "--config", type=str, default=None,
                        help='Config file')

    parser.add_argument("--pickle-file", type=str, default='db.pickle',
                        help='Name for the intermediate pickle file')

    parser.add_argument("--splat", type=str, default=None,
                        help=("Spectral scans will be scrunched into a single "
                              "channel containing data in the given frequency "
                              "range, starting from the frequency of the first"
                              " bin. E.g. '0:1000' indicates 'from the first "
                              "bin of the spectrum up to 1000 MHz above'. ':' "
                              "or 'all' for all the channels."))

    parser.add_argument("--refilt", default=False,
                        action='store_true',
                        help='Re-run the scan filtering')

    args = parser.parse_args(args)

    if args.sample_config:
        sample_config_file()
        sys.exit()

    assert args.config is not None, "Please specify the config file!"

    if not os.path.exists(args.pickle_file):
        get_full_table(args.config, plotall=True,
                       picklefile=args.pickle_file,
                       freqsplat=args.splat)

    with open(args.pickle_file, 'rb') as f:
        full_table = pickle.load(f)
        full_table.sort('Time')
    show_calibration(full_table)
