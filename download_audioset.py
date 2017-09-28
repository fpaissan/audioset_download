#!/usr/bin/env python
"""
Downloads Google's AudioSet dataset locally
"""
from __future__ import unicode_literals
import argparse
import csv
import logging, logging.handlers
import multiprocessing as mp
import os
import subprocess as sp
import sys
import traceback as tb
import urllib2
import multiprocessing_logging
import pafy
from cStringIO import StringIO


LOGGER = logging.getLogger('audiosetdl')
LOGGER.setLevel(logging.DEBUG)


def parse_arguments():
    """
    Parse arguments from the command line


    Returns:
        args:  Argument dictionary
               (Type: dict[str, str])
    """
    parser = argparse.ArgumentParser(description='Download AudioSet data locally')

    parser.add_argument('-f',
                        '--ffmpeg',
                        dest='ffmpeg_path',
                        action='store',
                        type=str,
                        default='./bin/ffmpeg/ffmpeg',
                        help='Path to ffmpeg executable')

    parser.add_argument('-e',
                        '--eval',
                        dest='eval_segments_url',
                        action='store',
                        type=str,
                        default='http://storage.googleapis.com/us_audioset/youtube_corpus/v1/csv/eval_segments.csv',
                        help='Path to evaluation segments file')

    parser.add_argument('-b',
                        '--balanced-train',
                        dest='balanced_train_segments_url',
                        action='store',
                        type=str,
                        default='http://storage.googleapis.com/us_audioset/youtube_corpus/v1/csv/balanced_train_segments.csv',
                        help='Path to balanced train segments file')

    parser.add_argument('-u',
                        '--unbalanced-train',
                        dest='unbalanced_train_segments_url',
                        action='store',
                        type=str,
                        default='http://storage.googleapis.com/us_audioset/youtube_corpus/v1/csv/unbalanced_train_segments.csv',
                        help='Path to unbalanced train segments file')

    parser.add_argument('-n',
                        '--num-workers',
                        dest='num_workers',
                        action='store',
                        type=int,
                        default=4,
                        help='Number of multiprocessing workers used to download videos')

    parser.add_argument('-nl',
                        '--no-logging',
                        dest='disable_logging',
                        action='store_true',
                        default=False,
                        help='Disables logging if flag enabled')

    parser.add_argument('-v',
                        '--verbose',
                        dest='verbose',
                        action='store_true',
                        default=False,
                        help='Prints verbose info to stdout')

    parser.add_argument('data_dir',
                        action='store',
                        type=str,
                        help='Path to directory where AudioSet data will be stored')


    return vars(parser.parse_args())


class SubprocessError(Exception):
    def __init__(self, cmd, return_code, stdout, stderr, *args):
        msg = 'Got non-zero exit code ({1}) from command "{0}": {2}'
        msg = msg.format(cmd[0], return_code, stderr)
        self.cmd = cmd
        self.cmd_return_code = return_code
        self.cmd_stdout = stdout
        self.cmd_stderr = stderr
        super(SubprocessError, self).__init__(msg, *args)


def run_command(cmd, shell=False, close_fds=False):
    proc = sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.PIPE,
                    shell=shell, close_fds=close_fds)
    stdout, stderr = proc.communicate()

    return_code = proc.returncode

    if return_code != 0:
        raise SubprocessError(cmd, return_code, stdout, stderr)

    return stdout, stderr, return_code


def ffmpeg(ffmpeg_path, input_path, output_path, input_args=None, output_args=None, log_level='error'):
    """
    Transform an input file using `ffmpeg`

    Args:
        ffmpeg_path:  Path to ffmpeg executable
                      (Type: str)

        input_path:   Path/URL to input file
                      (Type: str)

        output_path:  Path/URL to output file
                      (Type: str)

        input_args:
        output_args:
        log_level:

    Returns:

    """
    if not input_args:
        input_args = []
    if not output_args:
        output_args = []
    args = [ffmpeg_path] + input_args + ['-i', input_path] + output_args + [output_path, '-loglevel', log_level]

    try:
        stdout, stderr, retcode = run_command(args)
    except SubprocessError as e:
        if not e.cmd_stderr.endswith('already exists. Exiting.\n'):
            raise e
        LOGGER.info('ffmpeg output file "{}" already exists.'.format(output_path))




def download_yt_video(ytid, ts_start, output_dir, ffmpeg_path):
    """
    Download a Youtube video (with the audio and video separated).

    The audio will be saved in <output_dir>/audio and the video will be saved in
    <output_dir>/video.

    The output filename is of the format:
        <YouTube ID>_<start time in ms>_<end time in ms>.<extension>

    Args:
        ytid:         Youtube ID string
                      (Type: str)

        ts_start:     Segment start time (in seconds)
                      (Type: float)

        output_dir:   Output directory where video will be saved
                      (Type: str)

        ffmpeg_path:  Path to ffmpeg executable
                      (Type: str)
    """
    # Compute some things from the segment boundaries
    duration = 10
    ts_end = ts_start + duration
    tms_start, tms_end = int(ts_start * 1000), int(ts_end * 1000)

    # Make the output format and video URL
    # Output format is in the format:
    #   <YouTube ID>_<start time in ms>_<end time in ms>.<extension>
    basename_fmt = '{}_{}_{}'.format(ytid, tms_start, tms_end)
    video_filepath = os.path.join(output_dir, 'video', basename_fmt + '.mp4')
    audio_filepath = os.path.join(output_dir, 'audio', basename_fmt + '.flac')
    video_page_url = 'https://www.youtube.com/watch?v={}'.format(ytid)

    # Get the direct URLs to the videos with best audio and with best video (with audio)

    video = pafy.new(video_page_url)
    best_video = video.getbest()
    best_audio = video.getbestaudio()
    best_video_url = best_video.url
    best_audio_url = best_audio.url

    # Download the video and audio
    ffmpeg(ffmpeg_path, best_video_url, video_filepath,
           input_args=['-n', '-ss', str(ts_start)],
           output_args=['-t', str(duration),
                        '-f', 'mp4',
                        '-framerate', '30',
                        '-vcodec', 'h264'])
    ffmpeg(ffmpeg_path, best_audio_url, audio_filepath,
           input_args=['-n', '-ss', str(ts_start)],
           output_args=['-t', str(duration),
                        'ar', '44100',
                        '-vn',
                        '-ac', '2',
                        '-sample_fmt', 's16',
                        '-acodec', 'flac'])
    LOGGER.info('Downloaded video {} ({} - {})'.format(ytid, ts_start, ts_end))

    return video_filepath, audio_filepath


def segment_mp_worker(ytid, ts_start, data_dir, ffmpeg_path):
    """

        ytid:         Youtube ID string
                      (Type: str)

        ts_start:     Segment start time (in seconds)
                      (Type: float)

        data_dir:    Directory where videos will be saved
                      (Type: str)

        ffmpeg_path:  Path to ffmpeg executable
                      (Type: str)
    """
    ts_end = ts_start + 10
    LOGGER.info('Attempting to download video {} ({} - {})'.format(ytid, ts_start, ts_end))

    # Download the video
    try:
        download_yt_video(ytid, ts_start, data_dir, ffmpeg_path)
    except SubprocessError as e:
        err_msg = 'Error while downloading video {}: {}; {}'.format(ytid, e, tb.format_exc())
        LOGGER.error(err_msg)
        raise
    except Exception as e:
        err_msg = 'Error while processing video {}: {}; {}'.format(ytid, e, tb.format_exc())
        LOGGER.error(err_msg)
        raise


def download_subset_files(subset_url, data_dir, ffmpeg_path, num_workers):
    """
    Download subset segment file and videos

    Args:
        subset_url:   URL to subset segments file
                      (Type: str)

        data_dir:     Directory where dataset files will be saved
                      (Type: str)

        ffmpeg_path:  Path to ffmpeg executable
                      (Type: str)

        num_workers:  Number of multiprocessing workers used to download videos
                      (Type: int)
    """
    # Get filename of the subset file
    subset_filename = subset_url.split('/')[-1].split('?')[0]
    subset_path = os.path.join(data_dir, subset_filename)

    # Derive audio and video directory names for this subset
    data_dir = os.path.join(data_dir, 'data', os.path.splitext(subset_filename)[0])
    audio_dir = os.path.join(data_dir, 'audio')
    video_dir = os.path.join(data_dir, 'video')
    if not os.path.exists(audio_dir):
        os.makedirs(audio_dir)
    if not os.path.exists(video_dir):
        os.makedirs(video_dir)


    # Open subset file as a CSV
    if not os.path.exists(subset_path):
        with open(subset_path, 'wb') as f:
            subset_data = urllib2.urlopen(subset_url).read()
            f.write(subset_data)

    with open(subset_path, 'rb') as f:
        subset_data = csv.reader(f)

        # Set up multiprocessing pool
        pool = mp.Pool(num_workers)
        try:
            for row_idx, row in enumerate(subset_data):
                # Skip the 3 line header
                if row_idx < 3:
                    continue
                worker_args = [row[0], float(row[1]), data_dir, ffmpeg_path]
                pool.apply_async(segment_mp_worker, worker_args)
                break

        except csv.Error as e:
            err_msg = 'Encountered error in {} at line {}: {}'
            LOGGER.error(err_msg)
            sys.exit(err_msg.format(subset_filename, row_idx+1, e))
        finally:
            pool.close()
            pool.join()


def init_file_logger():
    """
    Initializes logging to a file.

    Saves log to "audiosetdl.log" in the current directory, and rotates them
    after they reach 1MiB.
    """
    # Set up file handler
    filename = 'audiosetdl.log'
    handler = logging.handlers.RotatingFileHandler(filename, maxBytes=2**20)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    LOGGER.addHandler(handler)


def init_console_logger(verbose):
    """
    Initializes logging to stdout

    Args:
        verbose:  If true, prints verbose information to stdout
                  (Type: bool)
    """
    # Log to stderr also
    stream_handler = logging.StreamHandler()
    if verbose:
        stream_handler.setLevel(logging.DEBUG)
    else:
        stream_handler.setLevel(logging.ERROR)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    stream_handler.setFormatter(formatter)
    LOGGER.addHandler(stream_handler)


def download_audioset(data_dir, ffmpeg_path, eval_segments_url,
                      balanced_train_segments_url, unbalanced_train_segments_url,
                      disable_logging, verbose, num_workers):
    """
    Download AudioSet files

    Args:
        data_dir:                       Directory where dataset files will
                                        be saved
                                        (Type: str)

        ffmpeg_path:                    Path to ffmpeg executable
                                        (Type: str)

        eval_segments_url:              Path to evaluation segments file
                                        (Type: str)

        balanced_train_segments_url:    Path to balanced train segments file
                                        (Type: str)

        unbalanced_train_segments_url:  Path to unbalanced train segments file
                                        (Type: str)

        disable_logging:                Disables logging to a file if True
                                        (Type: bool)

        verbose:                        Prints verbose information to stdout
                                        if True
                                        (Type: bool)

        num_workers:                    Number of multiprocessing workers used
                                        to download videos
                                        (Type: int)
    """
    init_console_logger(verbose)
    if not disable_logging:
        init_file_logger()
    multiprocessing_logging.install_mp_handler()
    LOGGER.debug('Initialized logging.')

    download_subset_files(eval_segments_url, data_dir, ffmpeg_path, num_workers)
    download_subset_files(balanced_train_segments_url, data_dir, ffmpeg_path, num_workers)
    download_subset_files(unbalanced_train_segments_url, data_dir, ffmpeg_path, num_workers)


if __name__ == '__main__':
    download_audioset(**parse_arguments())