# Copyright 2023 Iguazio
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import time

import mlrun.common.db.sql_session
import server.api.db.base
import server.api.utils.time_window_tracker


def test_time_window_tracker(db: server.api.db.base.DBInterface):
    db_session = mlrun.common.db.sql_session.create_session()
    max_window_size_seconds = 1
    time_tracker = server.api.utils.time_window_tracker.TimeWindowTracker(
        "test_key", max_window_size_seconds
    )
    time_tracker.initialize(db_session)
    timestamp_1 = time_tracker.get_window(db_session)
    # work happens here
    time_tracker.update_window(db_session)

    # assert initial value is not None
    assert timestamp_1 is not None
    stored_value = time_tracker._timestamp

    timestamp_2 = time_tracker.get_window(db_session)
    # work happens here
    time_tracker.update_window(db_session)

    # Check that the window is updated
    assert timestamp_2 > timestamp_1
    assert timestamp_2 == stored_value
    stored_value = time_tracker._timestamp

    time.sleep(max_window_size_seconds + 1)
    timestamp_3 = time_tracker.get_window(db_session)

    # Check that we got now - max_window_size_seconds and not the previously stored timestamp value
    assert timestamp_3 > timestamp_2
    assert timestamp_3 > stored_value
