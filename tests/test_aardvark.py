#!/usr/bin/env python

import nose
import array
from mock import patch, call, ANY
import pyaardvark
from pyaardvark.constants import *
from nose.tools import ok_, eq_, raises, assert_raises


@patch('pyaardvark.aardvark.api', autospec=True)
def test_api_version(api):
    v = pyaardvark.api_version()
    ok_(float(v) >= 5.3)

@patch('pyaardvark.aardvark.api', autospec=True)
def test_open_default(api):
    api.aa_open_ext.return_value = (42, (0,) * 6)
    a = pyaardvark.open()
    api.aa_open_ext.assert_called_once_with(0)
    eq_(a.handle, api.aa_open_ext.return_value[0])

@patch('pyaardvark.aardvark.api', autospec=True)
def test_find_devices_valid_devices(api):
    def f(num, devices):
        return 2

    def f_ext(num, num_ids, devices, ids):
        if num >= 2:
            devices[0] = 42 | pyaardvark.PORT_NOT_FREE
            ids[0] = 1234567890
            devices[1] = 4711
            ids[1] = 1111222222
        return 2

    api.aa_find_devices.side_effect = f
    api.aa_find_devices_ext.side_effect = f_ext

    devs = pyaardvark.find_devices()
    api.aa_find_devices.assert_has_calls([
        call(0, array.array('H')),
    ])
    api.aa_find_devices_ext.assert_has_calls([
        call(2, 2, ANY, ANY),
    ])
    eq_(len(devs), 2)
    eq_(devs[0]['port'], 42)
    eq_(devs[0]['serial_number'], '1234-567890')
    eq_(devs[0]['in_use'], True)
    eq_(devs[1]['port'], 4711)
    eq_(devs[1]['serial_number'], '1111-222222')
    eq_(devs[1]['in_use'], False)

@patch('pyaardvark.aardvark.api', autospec=True)
def test_open_port(api):
    api.aa_open_ext.return_value = (42, (0,) * 6)
    a = pyaardvark.open(4711)
    api.aa_open_ext.assert_called_once_with(4711)
    eq_(a.handle, api.aa_open_ext.return_value[0])

@patch('pyaardvark.aardvark.api', autospec=True)
def test_open_serial_number(api):
    devices = {
            42: 1234567890,
            4711: 1111222222,
            5: 3333444444,
    }

    def f(_num, devs):
        return len(devices)

    def f_ext(_num, _num_ids, devs, ids):
        for i, (dev, unique) in enumerate(devices.items()):
            if _num > i:
                devs[i] = dev
            if _num_ids > i:
                ids[i] = unique
        return len(devices)

    def open(handle):
        return (handle, (0,) * 6)

    def unique_id(handle):
        return devices[handle]

    api.aa_find_devices.side_effect = f
    api.aa_find_devices_ext.side_effect = f_ext
    api.aa_open_ext.side_effect = open
    api.aa_unique_id.side_effect = unique_id

    a = pyaardvark.open(serial_number='1234-567890')
    eq_(a.handle, 42)

    a = pyaardvark.open(serial_number='1111-222222')
    eq_(a.handle, 4711)

    assert_raises(IOError, pyaardvark.open, serial_number='7777-888888')

@patch('pyaardvark.aardvark.api', autospec=True)
def test_open_versions(api):
    api.aa_open_ext.return_value = (1, (0x101, 0x202, 0x303, 0, 0, 0))
    a = pyaardvark.open()
    eq_(a.api_version, '1.01')
    eq_(a.firmware_version, '2.02')
    eq_(a.hardware_revision, '3.03')

@patch('pyaardvark.aardvark.api', autospec=True)
@raises(IOError)
def test_open_error(api):
    api.aa_open_ext.return_value = (-1, (0,) * 6)
    pyaardvark.open()

@patch('pyaardvark.aardvark.api', autospec=True)
@raises(IOError)
def test_open_version_check_firmware(api):
    api.aa_open_ext.return_value = (1, (0, 100, 0, 0, 200, 0))
    pyaardvark.open()

@patch('pyaardvark.aardvark.api', autospec=True)
@raises(IOError)
def test_open_version_check_api(api):
    api.aa_open_ext.return_value = (1, (100, 0, 0, 200, 0, 0))
    pyaardvark.open()

@patch('pyaardvark.aardvark.api', autospec=True)
class TestAardvark(object):
    @patch('pyaardvark.aardvark.api', autospec=True)
    def setup(self, api):
        api.aa_open_ext.return_value = (1, (0,) * 6)
        self.a = pyaardvark.open()

    def test_close(self, api):
        handle = self.a.handle
        self.a.close()
        api.aa_close.assert_called_once_with(handle)

    def test_context_manager(self, api):
        api.aa_open_ext.return_value = (1, (0,) * 6)
        with pyaardvark.open() as a:
            eq_(a.handle, api.aa_open_ext.return_value[0])
            api.aa_open_ext.assert_called_once_with(0)
        api.aa_close.assert_called_once_with(
                api.aa_open_ext.return_value[0])

    def test_unique_id(self, api):
        api.aa_unique_id.return_value = 3627028473
        unique_id = self.a.unique_id()
        api.aa_unique_id.assert_called_once_with(self.a.handle)
        eq_(unique_id, api.aa_unique_id.return_value)

    def test_unique_id_str(self, api):
        api.aa_unique_id.return_value = 627008473
        unique_id_str = self.a.unique_id_str()
        api.aa_unique_id.assert_called_once_with(self.a.handle)
        eq_(unique_id_str, '0627-008473')

    def test_enable_i2c_1(self, api):
        api.aa_configure.return_value = CONFIG_SPI_GPIO
        eq_(self.a.enable_i2c, False)
        self.a.enable_i2c = True
        api.aa_configure.assert_called_with(self.a.handle, CONFIG_SPI_I2C)

    def test_enable_i2c_2(self, api):
        api.aa_configure.return_value = CONFIG_GPIO_ONLY
        eq_(self.a.enable_i2c, False)
        self.a.enable_i2c = True
        api.aa_configure.assert_called_with(self.a.handle, CONFIG_GPIO_I2C)

    def test_enable_i2c_3(self, api):
        api.aa_configure.return_value = CONFIG_GPIO_I2C
        eq_(self.a.enable_i2c, True)
        self.a.enable_i2c = False
        api.aa_configure.assert_called_with(self.a.handle, CONFIG_GPIO_ONLY)

    def test_enable_i2c_4(self, api):
        api.aa_configure.return_value = CONFIG_SPI_I2C
        eq_(self.a.enable_i2c, True)
        self.a.enable_i2c = False
        api.aa_configure.assert_called_with(self.a.handle, CONFIG_SPI_GPIO)

    @raises(IOError)
    def test_enable_i2c_error(self, api):
        api.aa_configure.return_value = -1
        self.a.enable_i2c = True

    def test_enable_spi_1(self, api):
        api.aa_configure.return_value = CONFIG_GPIO_I2C
        eq_(self.a.enable_spi, False)
        self.a.enable_spi = True
        api.aa_configure.assert_called_with(self.a.handle, CONFIG_SPI_I2C)

    def test_enable_spi_2(self, api):
        api.aa_configure.return_value = CONFIG_GPIO_ONLY
        eq_(self.a.enable_spi, False)
        self.a.enable_spi = True
        api.aa_configure.assert_called_with(self.a.handle, CONFIG_SPI_GPIO)

    def test_enable_spi_3(self, api):
        api.aa_configure.return_value = CONFIG_SPI_GPIO
        eq_(self.a.enable_spi, True)
        self.a.enable_spi = False
        api.aa_configure.assert_called_with(self.a.handle, CONFIG_GPIO_ONLY)

    def test_enable_spi_4(self, api):
        api.aa_configure.return_value = CONFIG_SPI_I2C
        eq_(self.a.enable_spi, True)
        self.a.enable_spi = False
        api.aa_configure.assert_called_with(self.a.handle, CONFIG_GPIO_I2C)

    @raises(IOError)
    def test_enable_spi_error(self, api):
        api.aa_configure.return_value = -1
        self.a.enable_spi = True

    def test_i2c_bitrate(self, api):
        api.aa_i2c_bitrate.return_value = 100
        self.a.i2c_bitrate = 4711
        eq_(self.a.i2c_bitrate, 100)

        api.aa_i2c_bitrate.assert_has_calls([
                call(self.a.handle, 4711),
                call(self.a.handle, 0),
        ])

    @raises(IOError)
    def test_i2c_bitrate_error(self, api):
        api.aa_i2c_bitrate.return_value = -1
        self.a.i2c_bitrate = 0

    def test_i2c_pullups(self, api):
        api.aa_i2c_pullup.return_value = 0
        self.a.i2c_pullups = False
        self.a.i2c_pullups = True
        pullup = self.a.i2c_pullups
        api.aa_i2c_pullup.assert_has_calls([
            call(self.a.handle, pyaardvark.I2C_PULLUP_NONE),
            call(self.a.handle, pyaardvark.I2C_PULLUP_BOTH),
            call(self.a.handle, pyaardvark.I2C_PULLUP_QUERY),
        ])

    @raises(IOError)
    def test_i2c_pullups_error(self, api):
        api.aa_i2c_pullup.return_value = -1
        _ = self.a.i2c_pullups

    def test_enable_target_power(self, api):
        api.aa_target_power.return_value = 0
        self.a.target_power = False
        self.a.target_power = True
        _ = self.a.target_power
        api.aa_target_power.assert_has_calls([
            call(self.a.handle, pyaardvark.TARGET_POWER_NONE),
            call(self.a.handle, pyaardvark.TARGET_POWER_BOTH),
            call(self.a.handle, pyaardvark.TARGET_POWER_QUERY),
        ])

    @raises(IOError)
    def test_enable_target_power_error(self, api):
        api.aa_target_power.return_value = -1
        self.a.target_power = 0

    def test_i2c_bus_timeout(self, api):
        api.aa_i2c_bus_timeout.return_value = 10
        self.a.i2c_bus_timeout = 300
        eq_(self.a.i2c_bus_timeout, 10)

        api.aa_i2c_bus_timeout.assert_has_calls([
                call(self.a.handle, 300),
                call(self.a.handle, 0),
        ])

    def test_i2c_master_write(self, api):
        addr = 0x50
        data = b'\x01\x02\x03'
        flags = pyaardvark.I2C_NO_STOP | pyaardvark.I2C_SIZED_READ
        api.aa_i2c_write_ext.return_value = (I2C_STATUS_OK, 3)
        self.a.i2c_master_write(addr, data, flags)
        api.aa_i2c_write_ext.assert_called_once_with(
                self.a.handle, addr, flags, len(data), array.array('B', data))

    def test_i2c_master_write_default_flags(self, api):
        api.aa_i2c_write_ext.return_value = (I2C_STATUS_OK, 0)
        self.a.i2c_master_write(0, b'')
        api.aa_i2c_write_ext.assert_called_once_with(
                ANY, ANY, pyaardvark.I2C_NO_FLAGS, ANY, ANY)

    @raises(IOError)
    def test_i2c_master_write_error(self, api):
        api.aa_i2c_write_ext.return_value = (I2C_STATUS_BUS_ERROR, 0)
        self.a.i2c_master_write(0, b'')

    def test_i2c_master_read(self, api):
        def i2c_master_read(_handle, _addr, _flags, length, data):
            eq_(data, array.array('B', (0,) * length))
            for i in range(length):
                data[i] = i
            return (I2C_STATUS_OK, length)

        addr = 0x50
        flags = pyaardvark.I2C_NO_STOP | pyaardvark.I2C_SIZED_READ
        api.aa_i2c_read_ext.side_effect = i2c_master_read
        data = self.a.i2c_master_read(addr, 3, flags)
        api.aa_i2c_read_ext.assert_called_once_with(
                self.a.handle, addr, flags, 3, ANY)
        eq_(data, b'\x00\x01\x02')

    def test_i2c_master_read_default_flags(self, api):
        api.aa_i2c_read_ext.return_value = (I2C_STATUS_OK, 1)
        _ = self.a.i2c_master_read(0, 0)
        api.aa_i2c_read_ext.assert_called_once_with(
                ANY, ANY, pyaardvark.I2C_NO_FLAGS, ANY, ANY)

    @raises(IOError)
    def test_i2c_master_read_error(self, api):
        api.aa_i2c_read_ext.return_value = (I2C_STATUS_BUS_ERROR, -1)
        self.a.i2c_master_read(0, 0)

    def test_i2c_master_write_read(self, api):
        def i2c_master_read(_handle, _addr, _flags, length, data):
            eq_(data, array.array('B', (0,) * length))
            for i in range(length):
                data[i] = i
            return (I2C_STATUS_OK, length)

        api.aa_i2c_write_ext.return_value = (I2C_STATUS_OK, 0)
        api.aa_i2c_read_ext.side_effect = i2c_master_read
        addr = 0x50
        data = self.a.i2c_master_write_read(addr, b'\x00\x01\x02', 3)
        api.aa_i2c_write_ext.assert_called_once_with(self.a.handle, addr,
                pyaardvark.I2C_NO_STOP, len(data), array.array('B', data))
        api.aa_i2c_read_ext.assert_called_once_with(
                self.a.handle, addr, pyaardvark.I2C_NO_FLAGS, 3, ANY)
        eq_(data, b'\x00\x01\x02')

    def test_i2c_master_write_read_default_flags(self, api):
        api.aa_i2c_read_ext.return_value = (I2C_STATUS_OK, 1)
        data = self.a.i2c_master_read(0, 0)
        api.aa_i2c_read_ext.assert_called_once_with(
                ANY, ANY, pyaardvark.I2C_NO_FLAGS, ANY, ANY)

    @raises(IOError)
    def test_i2c_master_write_read_error_read(self, api):
        api.aa_i2c_write_ext.return_value = (I2C_STATUS_OK, 1)
        api.aa_i2c_read_ext.return_value = (I2C_STATUS_BUS_ERROR, -1)
        self.a.i2c_master_write_read(0, b'', 0)

    @raises(IOError)
    def test_i2c_master_write_read_error_write(self, api):
        api.aa_i2c_write_ext.return_value = (I2C_STATUS_BUS_ERROR, -1)
        api.aa_i2c_read_ext.return_value = (I2C_STATUS_OK, 1)
        self.a.i2c_master_write_read(0, b'', 0)

    def test_enable_i2c_slave(self, api):
        api.aa_i2c_slave_enable.return_value = 0
        addr = 0x50
        self.a.enable_i2c_slave(addr)
        api.aa_i2c_slave_enable.assert_called_once_with(
                self.a.handle, addr, self.a.BUFFER_SIZE, self.a.BUFFER_SIZE)

    @raises(IOError)
    def test_enable_i2c_slave_error(self, api):
        api.aa_i2c_slave_enable.return_value = -1
        self.a.enable_i2c_slave(0)

    def test_disable_i2c_slave(self, api):
        api.aa_i2c_slave_disable.return_value = 0
        self.a.disable_i2c_slave()
        api.aa_i2c_slave_disable.assert_called_once_with(self.a.handle)

    @raises(IOError)
    def test_disable_i2c_slave_error(self, api):
        api.aa_i2c_slave_disable.return_value = -1
        self.a.disable_i2c_slave()

    def test_i2c_slave_read(self, api):
        addr = 0x50
        def i2c_slave_read(_handle, length, data):
            eq_(data, array.array('B', (0,) * length))
            length = 3
            for i in range(length):
                data[i] = i
            return (I2C_STATUS_OK, addr, length)

        api.aa_i2c_slave_read_ext.side_effect = i2c_slave_read
        ret = self.a.i2c_slave_read()
        api.aa_i2c_slave_read_ext.assert_called_once_with(
                self.a.handle, self.a.BUFFER_SIZE, ANY)
        eq_(ret, (addr, b'\x00\x01\x02'))

    @raises(IOError)
    def test_i2c_slave_read_error(self, api):
        api.aa_i2c_slave_read_ext.return_value = (-1, 0, I2C_STATUS_BUS_ERROR)
        self.a.i2c_slave_read()

    def test_i2c_slave_set_response(self, api):
        api.aa_i2c_slave_set_response.return_value = 0
        data = range(4)
        self.a.i2c_slave_response = data
        api.aa_i2c_slave_set_response.assert_called_once_with(
                self.a.handle, len(data), array.array('B', data))

    @raises(IOError)
    def test_i2c_slave_set_response_error(self, api):
        api.aa_i2c_slave_set_response.return_value = -1
        data = range(4)
        self.a.i2c_slave_response = data

    def test_last_transmit_size(self, api):
        expected_result = 23
        api.aa_i2c_slave_write_stats.return_value = expected_result
        actual_result = self.a.i2c_slave_last_transmit_size
        api.aa_i2c_slave_write_stats.assert_called_once_with(self.a.handle)
        eq_(actual_result, expected_result)

    @raises(IOError)
    def test_last_transmit_size_error(self, api):
        api.aa_i2c_slave_write_stats.return_value = -1
        _ = self.a.i2c_slave_last_transmit_size

    def test_enable_i2c_monitor(self, api):
        api.aa_i2c_monitor_enable.return_value = 0
        self.a.enable_i2c_monitor()
        api.aa_i2c_monitor_enable.assert_called_once_with(self.a.handle)

    @raises(IOError)
    def test_enable_i2c_monitor_error(self, api):
        api.aa_i2c_monitor_enable.return_value = -1
        self.a.enable_i2c_monitor()

    def test_disable_i2c_monitor(self, api):
        api.aa_i2c_monitor_disable.return_value = 0
        self.a.disable_i2c_monitor()
        api.aa_i2c_monitor_disable.assert_called_once_with(self.a.handle)

    @raises(IOError)
    def test_disable_i2c_monitor_error(self, api):
        api.aa_i2c_monitor_disable.return_value = -1
        self.a.disable_i2c_monitor()

    def test_i2c_monitor_read(self, api):
        def i2c_monitor_read(_handle, length, data):
            eq_(data, array.array('B', (0,) * length))
            length = 3
            for i in range(length):
                data[i] = i
            return length

        api.aa_i2c_monitor_read.side_effect = i2c_monitor_read
        ret = self.a.i2c_monitor_read()
        api.aa_i2c_monitor_read.assert_called_once_with(
                self.a.handle, self.a.BUFFER_SIZE, ANY)
        eq_(ret, ([0, 1, 2]))

    @raises(IOError)
    def test_i2c_monitor_read_error(self, api):
        api.aa_i2c_monitor_read.return_value = -1
        self.a.i2c_monitor_read()

    def test_spi_bitrate(self, api):
        api.aa_spi_bitrate.return_value = 1000
        self.a.spi_bitrate = 4711
        eq_(self.a.spi_bitrate, 1000)

        api.aa_spi_bitrate.assert_has_calls([
                call(self.a.handle, 4711),
                call(self.a.handle, 0),
        ])

    @raises(IOError)
    def test_spi_bitrate_error(self, api):
        api.aa_spi_bitrate.return_value = -1
        self.a.spi_bitrate = 0

    def test_spi_configure(self, api):
        api.aa_spi_configure.return_value = 0
        self.a.spi_configure(1, 2, 3)
        api.aa_spi_configure.assert_called_once_with(self.a.handle, 1, 2, 3)

    @raises(IOError)
    def test_spi_configure_error(self, api):
        api.aa_spi_configure.return_value = -1
        self.a.spi_configure(0, 0, 0)

    def test_spi_configure_mode_0(self, api):
        api.aa_spi_configure.return_value = 0
        self.a.spi_configure_mode(pyaardvark.SPI_MODE_0)
        api.aa_spi_configure.assert_called_once_with(self.a.handle, 0, 0, 0)

    def test_spi_configure_mode_3(self, api):
        api.aa_spi_configure.return_value = 0
        self.a.spi_configure_mode(pyaardvark.SPI_MODE_3)
        api.aa_spi_configure.assert_called_once_with(self.a.handle, 1, 1, 0)

    @raises(IOError)
    def test_spi_configure_mode_error(self, api):
        api.aa_spi_configure.return_value = -1
        self.a.spi_configure_mode(0)

    @raises(RuntimeError)
    def test_spi_configure_mode_unknown_mode(self, api):
        self.a.spi_configure_mode(1)

    def test_spi_ss_polarity(self, api):
        api.aa_spi_master_ss_polarity.return_value = 0
        self.a.spi_ss_polarity(42)
        api.aa_spi_master_ss_polarity.assert_called_once_with(self.a.handle, 42)

    @raises(IOError)
    def test_spi_ss_polarity_error(self, api):
        api.aa_spi_master_ss_polarity.return_value = -1
        self.a.spi_ss_polarity(0)

    def test_spi_spi_write(self, api):
        def spi_write(_handle, len_tx, tx, len_rx, rx):
            eq_(len_tx, len_rx)
            for i, v in enumerate(reversed(tx)):
                rx[i] = v
            return len_tx
        api.aa_spi_write.side_effect = spi_write
        data = b'\x01\x02\x03'
        rx_data = self.a.spi_write(data)
        eq_(rx_data, data[::-1])
        api.aa_spi_write.assert_called_once_with(self.a.handle, len(data),
                array.array('B', data), len(data), ANY)

    @raises(IOError)
    def test_spi_spi_write_error(self, api):
        api.aa_spi_write.return_value = -1
        self.a.spi_write(b'')

    def test_configured_gpio_ports_identical(self, api):
        used_gpios = []
        api.py_aa_gpio_direction.return_value = 0
        self.a.configured_gpio_outputs = used_gpios
        assert api.py_aa_gpio_direction.call_count == 0
        eq_(self.a.configured_gpio_outputs, used_gpios)

    def test_configured_gpio_ports_changed(self, api):
        api.py_aa_gpio_direction.return_value = 0
        used_gpios = [GPIO_SCK, GPIO_SCL]
        self.a.configured_gpio_outputs = used_gpios
        api.py_aa_gpio_direction.assert_called_once_with(self.a.handle, sum(used_gpios))
        eq_(self.a.configured_gpio_outputs, used_gpios)

    @raises(IOError)
    def test_configured_gpio_ports_changed_error(self, api):
        api.py_aa_gpio_direction.return_value = -1
        self.a.configured_gpio_outputs = [GPIO_SDA, GPIO_SCL]

    def test_gpio_clear(self, api):
        api.py_aa_gpio_set.return_value = 0
        self.a.gpio_clear(GPIO_SS)
        assert api.py_aa_gpio_set.call_count == 0

    def test_gpio_set_clear(self, api):
        gpio = GPIO_SS
        api.py_aa_gpio_set.return_value = 0
        self.a.gpio_set(gpio)
        self.a.gpio_clear(gpio)
        api.py_aa_gpio_set.assert_has_calls([call(self.a.handle, gpio),
                                             call(self.a.handle,    0)])

    @raises(IOError)
    def test_gpio_set_clear_error(self, api):
        gpio = GPIO_SS
        api.py_aa_gpio_set.return_value = 0
        self.a.gpio_set(gpio)
        api.py_aa_gpio_set.return_value = -1
        self.a.gpio_clear(gpio)

    @raises(IOError)
    def test_gpio_set_error(self, api):
        api.py_aa_gpio_set.return_value = -1
        self.a.gpio_set(GPIO_SDA)

    def test_gpio_set_set(self, api):
        gpio = GPIO_MISO
        api.py_aa_gpio_set.return_value = 0
        self.a.gpio_set(gpio)
        self.a.gpio_set(gpio)
        api.py_aa_gpio_set.assert_called_once_with(self.a.handle, gpio)

    def test_gpio_toggle_once(self, api):
        gpio = GPIO_MOSI
        api.py_aa_gpio_set.return_value = 0
        self.a.gpio_toggle(gpio)
        api.py_aa_gpio_set.assert_called_once_with(self.a.handle, gpio)

    def test_gpio_toggle_twice(self, api):
        gpio = GPIO_SCK
        api.py_aa_gpio_set.return_value = 0
        self.a.gpio_toggle(gpio)
        self.a.gpio_toggle(gpio)
        api.py_aa_gpio_set.assert_has_calls([call(self.a.handle, gpio),
                                             call(self.a.handle,    0)])

    def test_gpio_toggle_thrice(self, api):
        gpio = GPIO_SCL
        api.py_aa_gpio_set.return_value = 0
        self.a.gpio_toggle(gpio)
        self.a.gpio_toggle(gpio)
        self.a.gpio_toggle(gpio)
        api.py_aa_gpio_set.assert_has_calls([call(self.a.handle, gpio),
                                             call(self.a.handle,    0),
                                             call(self.a.handle, gpio)])

    @raises(IOError)
    def test_gpio_toggle_error(self, api):
        api.py_aa_gpio_set.return_value = -1
        self.a.gpio_toggle(GPIO_SCK)

    def test_enabled_gpio_pullups_identical(self, api):
        used_gpios = []
        api.py_aa_gpio_pullup.return_value = 0
        self.a.enabled_gpio_pullups = used_gpios
        assert api.py_aa_gpio_pullup.call_count == 0
        eq_(self.a.enabled_gpio_pullups, used_gpios)

    def test_enabled_gpio_pullups_changed(self, api):
        used_gpios = [GPIO_SDA, GPIO_SCL]
        api.py_aa_gpio_pullup.return_value = 0
        self.a.enabled_gpio_pullups = used_gpios
        api.py_aa_gpio_pullup.assert_called_with(self.a.handle, sum(used_gpios))
        eq_(self.a.enabled_gpio_pullups, used_gpios)

    @raises(IOError)
    def test_enabled_gpio_pullups_changed_error(self, api):
        used_gpios = [GPIO_SDA, GPIO_SCL]
        api.py_aa_gpio_pullup.return_value = -1
        self.a.enabled_gpio_pullups = used_gpios
        api.py_aa_gpio_pullup.assert_called_with(self.a.handle, sum(used_gpios))
        eq_(self.a.enabled_gpio_pullups, used_gpios)

    def test_gpio_poll(self, api):
        high_gpios = [GPIO_SCK, GPIO_SS]
        api.py_aa_gpio_change.return_value = sum(high_gpios)
        timeout = 42
        ret = self.a.gpio_poll(timeout)
        api.py_aa_gpio_change.assert_called_once_with(self.a.handle, timeout)
        eq_(ret, high_gpios)

    @raises(IOError)
    def test_gpio_poll_error(self, api):
        api.py_aa_gpio_change.return_value = -1
        timeout = 23
        self.a.gpio_poll(timeout)
        api.py_aa_gpio_change.assert_called_once_with(self.a.handle, timeout)

    def test_gpio_get_output_low(self, api):
        gpio = GPIO_MOSI
        api.py_aa_gpio_direction.return_value = 0
        self.a.configured_gpio_outputs = [gpio]
        ret = self.a.gpio_get(gpio)
        eq_(ret, False)

    def test_gpio_get_output_high(self, api):
        gpio = GPIO_MISO
        api.py_aa_gpio_direction.return_value = 0
        self.a.configured_gpio_outputs = [gpio]
        api.py_aa_gpio_set.return_value = 0
        self.a.gpio_set(gpio)
        ret = self.a.gpio_get(gpio)
        eq_(ret, True)

    def test_gpio_get_input_low(self, api):
        api.py_aa_gpio_change.return_value = 0
        ret = self.a.gpio_get(GPIO_SCL)
        eq_(ret, False)

    def test_gpio_get_input_high(self, api):
        gpio = GPIO_SDA
        api.py_aa_gpio_change.return_value = GPIO_SDA
        ret = self.a.gpio_get(gpio)
        eq_(ret, True)

if __name__ == '__main__':
    nose.main()
