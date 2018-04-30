from appium import webdriver
import pytest
import os
import re

import testharness
import wbcv

projects = ['pachinko', 'unicorn', 'ronin']
collect_ignore = []

# Appium fixture
@pytest.fixture(scope='session')
def appium_server():
    url = 'http://127.0.0.1:4723/wd/hub'
    desiredCaps = {}
    push_files()
    driver = webdriver.Remote(url,  desiredCaps)
    yield driver
    try:
        driver.quit()
    except:
        pass

# ImageDetect fixture
@pytest.fixture(scope='session')
def image_detect(appium_server):
    sc = wbcv.streamcatcher.StreamCatcher(appiumServer = appium_server,
                                          ffmpegBinary = 'ffmpeg/ffmpeg')
    id = wbcv.imagedetect.ImageDetect(streamCatcher = sc)
    id.streamCatcher.stream_start()
    yield id
    id.quit()

# Utility fixture
@pytest.fixture(scope='session')
def utility(appium_server, image_detect):
    return testharness.Utility(screenshotPath = os.getenv('SCREENSHOT_PATH', ''),
                               appiumServer = appium_server,
                               imageDetect = image_detect)

def pytest_cmdline_preparse(args):
    '''
    Fix for AWS running test steps as separate sessions.
    '''
    if '--collect-only' in args:
        for p in projects:
            collect_ignore.append('tests/{}/'.format(p))
    else:
        collect_ignore.append('tests/test_a.py')
        if '--pdb' not in args:
            args[:] = ['-vrx']
            args[:] = ['--junit-xml=test_report.xml'] + args
            args[:] = ['tests/'] + args

def push_files():
    '''
    Pushes files found in the sdcard folder to the device.
    '''
    if os.path.isdir('sdcard/'):

        from subprocess import call

        for path, dirs, files in os.walk('sdcard/'):
            for f in files:
                targetFile = os.path.join(path, f)
                call(['adb', 'push', targetFile, '/{}'.format(targetFile.replace('\\', '/'))])
    return

# Custom marks
# Note that these are executed in the order of the list
# Marks that have a bigger impact on the test should come first
# Each custom mark needs 3 methods
# If the method is not used by the mark, it does not need to be defined
# Needed methods:
#     - _<mark>_setup(item)
#         - Is called unconditionally before the test step is run
#     - _<mark>_setup_marked(item, *args, **kwargs)
#         - Is called before the test step is run but only if marked
#         - Is called after _<mark>_setup
#     - _<mark>_makereport(item, call, *args, **kwargs)
#         - Is called after the test step ran but only if marked
customMarks = ['critical', 'require', 'sequence', 'requirement']

# Requirement

def _requirement_makereport(item, call, name):

    # If there was an error
    if call.excinfo is not None:
        # Create the failed set
        if not hasattr(item.session, '_requirementFailure'):
            item.session._requirementFailure = set()
        # If requirement is parametrized
        if item.name.endswith(']'):
            name = name + item.name[item.name.find('['):]
        # Add requirement name to list of failed requirements
        item.session._requirementFailure.add(name)

# Require

def _require_setup_marked(item, name):

    # If any requirements failed
    if hasattr(item.session, '_requirementFailure'):
        if item.name.endswith(']'):
            nameParametrized = name + item.name[item.name.find('['):]
        else:
            nameParametrized = name
        # If this requirement failed
        for n in [name, nameParametrized]:
            if n in item.session._requirementFailure:
                pytest.xfail('Requirement failure, requirement "{}" did not pass.'.format(n))

# Critical

def _critical_setup(item):

    if hasattr(item.session, '_criticalFailure'):
        pytest.xfail('Critical failure, test "{}" did not pass.'.format(item.session._criticalFailure.name))

def _critical_makereport(item, call):

    if call.excinfo is not None and not hasattr(item.session, '_criticalFailure'):
        item.session._criticalFailure = item

# Sequence

def _sequence_setup(item):

    if 'sequence' not in item.keywords:
        item.session._sequenceFailure = None

def _sequence_setup_marked(item):

    if getattr(item.session, '_sequenceFailure', None) is not None:
        failed = False
        if item.name.endswith(']'):
            if item.session._sequenceFailure.name.endswith(item.name[item.name.find('['):]):
                failed = True
        else:
            failed = True
        if failed:
            pytest.xfail('Sequence failure, test "{}" did not pass.'.format(item.session._sequenceFailure.name))

def _sequence_makereport(item, call):

    if call.excinfo is not None and getattr(item.session, '_sequenceFailure', None) is None:
        item.session._sequenceFailure = item

# Pytest hooks

def pytest_runtest_setup(item):

    # _setup
    for mark in customMarks:
        try:
            method = eval('_' + mark + '_setup')
        except:
            method = None
        if method is not None:
            method(item)
    # _setup_marked
    for mark in customMarks:
        if mark in item.keywords:
            try:
                method = eval('_' + mark + '_setup_marked')
            except:
                method = None
            if method is not None:
                method(item, *item.keywords[mark].args, **item.keywords[mark].kwargs)

def pytest_runtest_makereport(item, call):

    # _makereport
    for mark in customMarks:
        if mark in item.keywords:
            try:
                method = eval('_' + mark + '_makereport')
            except:
                method = None
            if method is not None:
                method(item, call, *item.keywords[mark].args, **item.keywords[mark].kwargs)
