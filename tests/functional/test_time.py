"""Time class functional tests"""
import datetime

from curldl.util import Time


def test_timestamp_to_dt() -> None:
    """datetime returned for epoch start"""
    dt_epoch = Time.timestamp_to_dt(0)
    dt_expected = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)
    dt_expected_utc2 = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone(datetime.timedelta(hours=2)))
    assert dt_epoch == dt_expected != dt_expected_utc2
    assert dt_epoch.utcoffset() == datetime.timedelta()


def test_timestamp_to_dt_float() -> None:
    """datetime returned for floating-point seconds"""
    dt_2hrs = Time.timestamp_to_dt(7200.5)
    dt_expected_utc2 = datetime.datetime(1970, 1, 1, 2, microsecond=500000, tzinfo=datetime.timezone.utc)
    assert dt_2hrs == dt_expected_utc2


def test_timestamp_to_dt_arbitrary() -> None:
    """datetime returned for arbitrary floating-point seconds"""
    dt_arbitrary = Time.timestamp_to_dt(1234567890.123456)
    dt_expected = datetime.datetime(2009, 2, 13, 23, 31, 30, 123456, tzinfo=datetime.timezone.utc)
    assert dt_arbitrary == dt_expected


def test_timestamp_to_http_date() -> None:
    """HTTP Date returned for arbitrary integer seconds"""
    http_date = Time.timestamp_to_http_date(1234567890)
    http_date_expected = 'Fri, 13 Feb 2009 23:31:30 GMT'
    assert http_date == http_date_expected


def test_timestamp_to_http_date_float() -> None:
    """HTTP Date returned for arbitrary floating-point seconds"""
    http_date1 = Time.timestamp_to_http_date(1234567890.123456)
    http_date2 = Time.timestamp_to_http_date(1234567889.654321)
    http_date_expected = 'Fri, 13 Feb 2009 23:31:30 GMT'
    assert http_date1 == http_date2 == http_date_expected


def test_timestamp_delta_basic() -> None:
    """Time delta returned for integer seconds under 1 day"""
    time_delta = Time.timestamp_delta(12345)
    td_expected_str = '3:25:45'
    assert str(time_delta) == td_expected_str


def test_timestamp_delta_arbitrary() -> None:
    """Time delta returned for arbitrary integer seconds"""
    time_delta = Time.timestamp_delta(1234567890)
    td_expected_str = '14288 days, 23:31:30'
    assert str(time_delta) == td_expected_str


def test_timestamp_delta_float() -> None:
    """Time delta returned for floating-point seconds"""
    time_delta1 = Time.timestamp_delta(1234567890.12345)
    time_delta2 = Time.timestamp_delta(1234567889.54321)
    td_expected_str = '14288 days, 23:31:30'
    assert str(time_delta1) == str(time_delta2) == td_expected_str
