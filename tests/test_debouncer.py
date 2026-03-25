import time
from unittest.mock import Mock
from chronicler.core.debouncer import Debouncer

def test_single_event_fires_after_delay():
    callback = Mock()
    db = Debouncer(delay_seconds=0.1, callback=callback)
    db.trigger("file.py")
    time.sleep(0.3)
    callback.assert_called_once_with("file.py")

def test_burst_events_coalesce_to_one():
    callback = Mock()
    db = Debouncer(delay_seconds=0.2, callback=callback)
    for _ in range(5):
        db.trigger("file.py")
        time.sleep(0.05)
    time.sleep(0.5)
    callback.assert_called_once_with("file.py")

def test_two_different_files_both_fire():
    callback = Mock()
    db = Debouncer(delay_seconds=0.1, callback=callback)
    db.trigger("a.py")
    db.trigger("b.py")
    time.sleep(0.4)
    paths = {call.args[0] for call in callback.call_args_list}
    assert "a.py" in paths and "b.py" in paths

def test_shutdown_cancels_pending():
    callback = Mock()
    db = Debouncer(delay_seconds=1.0, callback=callback)
    db.trigger("file.py")
    db.shutdown()
    callback.assert_not_called()
