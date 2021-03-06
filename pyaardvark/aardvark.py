# Copyright (c) 2014-2018  Kontron Europe GmbH
#               2017       CAMCO Produktions- und Vertriebs-GmbH
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA

from builtins import bytes
import array
import logging
import sys
import aardvark_py as api

from .constants import *

log = logging.getLogger(__name__)

def _raise_error_if_negative(val):
    """Raises an :class:`IOError` if `val` is negative."""
    if val < 0:
        raise IOError(val, api.aa_status_string(val))

def status_string(code):
    for k, v in globals().items():
        if k.startswith('I2C_STATUS_') and v == code:
            return k
    return 'I2C_STATUS_UNKNOWN_STATUS'

def _raise_i2c_status_code_error_if_failure(code):
    """Raises an :class:`IOError` if `code` is not :data:`I2C_STATUS_OK`."""
    if code != I2C_STATUS_OK:
        raise IOError(code, status_string(code))

def _unique_id_str(unique_id):
    id1 = unique_id / 1000000
    id2 = unique_id % 1000000
    return '%04d-%06d' % (id1, id2)

def _to_version_str(v):
    return '%d.%02d' % (v >> 8, v & 0xff)

def api_version():
    """Returns the underlying C module (aardvark.so, aardvark.pyd) as a string.

    It returns the same value as :attr:`Aardvark.api_version` but you don't
    need to open a device.
    """
    return _to_version_str(api.AA_SW_VERSION)

def find_devices():
    """Return a list of dictionaries. Each dictionary represents one device.

    The dictionary contains the following keys: port, unique_id and in_use.
    `port` can be used with :func:`open`. `serial_number` is the serial number
    of the device (and can also be used with :func:`open`) and `in_use`
    indicates whether the device was opened before and can currently not be
    opened.

    .. note::

       There is no guarantee, that the returned information is still valid
       when you open the device. Esp. if you open a device by the port, the
       unique_id may change because you've just opened another device. Eg. it
       may be disconnected from the machine after you call :func:`find_devices`
       but before you call :func:`open`.

       To open a device by its serial number, you should use the :func:`open`
       with the `serial_number` parameter.
    """

    # first fetch the number of attached devices, so we can create a buffer
    # with the exact amount of entries. api expects array of u16
    num_devices = api.aa_find_devices(array.array('H'))[0]
    _raise_error_if_negative(num_devices)

    # return an empty list if no device is connected
    if num_devices == 0:
        return list()

    ports = array.array('H', (0,) * num_devices)
    unique_ids = array.array('I', (0,) * num_devices)
    (num_devices, ports, unique_ids) = api.aa_find_devices_ext(ports, unique_ids)
    _raise_error_if_negative(num_devices)
    if num_devices == 0:
        return list()

    del ports[num_devices:]
    del unique_ids[num_devices:]

    devices = list()
    for port, uid in zip(ports, unique_ids):
        in_use = bool(port & PORT_NOT_FREE)
        dev = dict(
                port=port & ~PORT_NOT_FREE,
                serial_number=_unique_id_str(uid),
                in_use=in_use)
        devices.append(dev)

    return devices

def open(port=None, serial_number=None):
    """Open an aardvark device and return an :class:`Aardvark` object. If the
    device cannot be opened an :class:`IOError` is raised.

    The `port` can be retrieved by :func:`find_devices`. Usually, the first
    device is 0, the second 1, etc.

    If you are using only one device, you can therefore omit the parameter
    in which case 0 is used.

    Another method to open a device is to use the serial number. You can either
    find the number on the device itself or in the in the corresponding USB
    property. The serial number is a string which looks like `NNNN-MMMMMMM`.

    Raises an :class:`IOError` if the port (or serial number) does not exist,
    is already connected or an incompatible device is found.

    .. note::

       There is a small chance that this function raises an :class:`IOError`
       although the correct device is available and not opened. The
       open-by-serial-number method works by scanning the devices. But as
       explained in :func:`find_devices`, the returned information may be
       outdated. Therefore, :func:`open` checks the serial number once the
       device is opened and if it is not the expected one, raises
       :class:`IOError`. No retry mechanism is implemented.

       As long as nobody comes along with a better idea, this failure case is
       up to the user.
    """
    if port is None and serial_number is None:
        dev = Aardvark()
    elif serial_number is not None:
        for d in find_devices():
            if d['serial_number'] == serial_number:
                break
        else:
            _raise_error_if_negative(ERR_UNABLE_TO_OPEN)

        dev = Aardvark(d['port'])

        # make sure we opened the correct device
        if dev.unique_id_str() != serial_number:
            dev.close()
            _raise_error_if_negative(ERR_UNABLE_TO_OPEN)
    else:
        dev = Aardvark(port)

    return dev

class Aardvark(object):
    """Represents an Aardvark device."""
    BUFFER_SIZE = 65535

    def __init__(self, port=0):
        ret, ver = api.aa_open_ext(port)
        _raise_error_if_negative(ret)

        #: A handle which is used as the first paramter for all calls to the
        #: underlying API.
        self.handle = ret

        # assign some useful names
        version = dict(
            software = ver.version.software,
            firmware = ver.version.firmware,
            hardware = ver.version.hardware,
            sw_req_by_fw = ver.version.sw_req_by_fw,
            fw_req_by_sw = ver.version.fw_req_by_sw,
            api_req_by_sw = ver.version.api_req_by_sw
        )

        #: Hardware revision of the host adapter as a string. The format is
        #: ``M.NN`` where `M` is the major number and `NN` the zero padded
        #: minor number.
        self.hardware_revision = _to_version_str(version['hardware'])

        #: Firmware version of the host adapter as a string. See
        #: :attr:`hardware_revision` for more information on the format.
        self.firmware_version = _to_version_str(version['firmware'])

        #: Version of underlying C module (aardvark.so, aardvark.pyd) as a
        #: string. See :attr:`hardware_revision` for more information on the
        #: format.
        self.api_version = _to_version_str(version['software'])

        # version checks
        if version['firmware'] < version['fw_req_by_sw']:
            log.debug('The API requires a firmware version >= %s, but the '
                    'device has version %s',
                    _to_version_str(version['fw_req_by_sw']),
                    _to_version_str(version['firmware']))
            ret = ERR_INCOMPATIBLE_DEVICE
        elif version['software'] < version['sw_req_by_fw']:
            log.debug('The firmware requires an API version >= %s, but the '
                    'API has version %s',
                    _to_version_str(version['sw_req_by_fw']),
                    _to_version_str(version['software']))
            ret = ERR_INCOMPATIBLE_LIBRARY
        _raise_error_if_negative(ret)

        # Initialize Aardvark to a well-known state
        # SPI/I2C is the default configuration after power-cycle
        self._interface_configuration(CONFIG_SPI_I2C)

        # Initialize shadow variables
        self._i2c_slave_response = None
        self._configured_gpio_outputs = []
        self._high_gpio_outputs = []
        self._enabled_gpio_pullups = []

    def __enter__(self):
        return self

    def __exit__(self, type, value, tb):
        self.close()
        return False

    def close(self):
        """Close the device."""

        api.aa_close(self.handle)
        self.handle = None

    def unique_id(self):
        """Return the unique identifier of the device. The identifier is the
        serial number you can find on the adapter without the dash. Eg. the
        serial number 0012-345678 would be 12345678.
        """
        return api.aa_unique_id(self.handle)

    def unique_id_str(self):
        """Return the unique identifier. But unlike :func:`unique_id`, the ID
        is returned as a string which has the format NNNN-MMMMMMM.
        """
        return _unique_id_str(self.unique_id())

    def _interface_configuration(self, value):
        ret = api.aa_configure(self.handle, value)
        _raise_error_if_negative(ret)
        return ret

    @property
    def enable_i2c(self):
        """Set this to `True` to enable the hardware I2C interface. If set to
        `False` the hardware interface will be disabled and its pins (SDA and
        SCL) can be used as GPIOs.
        """
        config = self._interface_configuration(CONFIG_QUERY)
        return config == CONFIG_GPIO_I2C or config == CONFIG_SPI_I2C

    @enable_i2c.setter
    def enable_i2c(self, value):
        new_config = config = self._interface_configuration(CONFIG_QUERY)
        if value and config == CONFIG_GPIO_ONLY:
            new_config = CONFIG_GPIO_I2C
        elif value and config == CONFIG_SPI_GPIO:
            new_config = CONFIG_SPI_I2C
        elif not value and config == CONFIG_GPIO_I2C:
            new_config = CONFIG_GPIO_ONLY
        elif not value and config == CONFIG_SPI_I2C:
            new_config = CONFIG_SPI_GPIO
        if new_config != config:
            self._interface_configuration(new_config)

    @property
    def enable_spi(self):
        """Set this to `True` to enable the hardware SPI interface. If set to
        `False` the hardware interface will be disabled and its pins (MISO,
        MOSI, SCK and SS) can be used as GPIOs.
        """
        config = self._interface_configuration(CONFIG_QUERY)
        return config == CONFIG_SPI_GPIO or config == CONFIG_SPI_I2C

    @enable_spi.setter
    def enable_spi(self, value):
        new_config = config = self._interface_configuration(CONFIG_QUERY)
        if value and config == CONFIG_GPIO_ONLY:
            new_config = CONFIG_SPI_GPIO
        elif value and config == CONFIG_GPIO_I2C:
            new_config = CONFIG_SPI_I2C
        elif not value and config == CONFIG_SPI_GPIO:
            new_config = CONFIG_GPIO_ONLY
        elif not value and config == CONFIG_SPI_I2C:
            new_config = CONFIG_GPIO_I2C
        if new_config != config:
            self._interface_configuration(new_config)

    @property
    def i2c_bitrate(self):
        """I2C bitrate in kHz. Not every bitrate is supported by the host
        adapter. Therefore, the actual bitrate may be less than the value which
        is set.

        The power-on default value is 100 kHz.
        """

        ret = api.aa_i2c_bitrate(self.handle, 0)
        _raise_error_if_negative(ret)
        return ret

    @i2c_bitrate.setter
    def i2c_bitrate(self, value):
        ret = api.aa_i2c_bitrate(self.handle, value)
        _raise_error_if_negative(ret)

    @property
    def i2c_pullups(self):
        """Setting this to `True` will enable the I2C pullup resistors. If set
        to `False` the pullup resistors will be disabled.

        Raises an :exc:`IOError` if the hardware adapter does not support
        pullup resistors.
        """
        ret = api.aa_i2c_pullup(self.handle, I2C_PULLUP_QUERY)
        _raise_error_if_negative(ret)
        return ret

    @i2c_pullups.setter
    def i2c_pullups(self, value):
        if value:
            pullup = I2C_PULLUP_BOTH
        else:
            pullup = I2C_PULLUP_NONE
        ret = api.aa_i2c_pullup(self.handle, pullup)
        _raise_error_if_negative(ret)

    @property
    def target_power(self):
        """Setting this to `True` will activate the power pins (4 and 6). If
        set to `False` the power will be deactivated.

        Raises an :exc:`IOError` if the hardware adapter does not support
        the switchable power pins.
        """
        ret = api.aa_target_power(self.handle, TARGET_POWER_QUERY)
        _raise_error_if_negative(ret)
        return ret

    @target_power.setter
    def target_power(self, value):
        if value:
            power = TARGET_POWER_BOTH
        else:
            power = TARGET_POWER_NONE
        ret = api.aa_target_power(self.handle, power)
        _raise_error_if_negative(ret)

    @property
    def i2c_bus_timeout(self):
        """I2C bus lock timeout in ms.

        Minimum value is 10 ms and the maximum value is 450 ms. Not every value
        can be set and will be rounded to the next possible number. You can
        read back the property to get the actual value.

        The power-on default value is 200 ms.
        """
        ret = api.aa_i2c_bus_timeout(self.handle, 0)
        _raise_error_if_negative(ret)
        return ret

    @i2c_bus_timeout.setter
    def i2c_bus_timeout(self, timeout):
        ret = api.aa_i2c_bus_timeout(self.handle, timeout)
        _raise_error_if_negative(ret)

    def i2c_master_write(self, i2c_address, data, flags=I2C_NO_FLAGS):
        """Make an I2C write access.

        The given I2C device is addressed and data given as a string is
        written. The transaction is finished with an I2C stop condition unless
        I2C_NO_STOP is set in the flags.

        10 bit addresses are supported if the I2C_10_BIT_ADDR flag is set.
        """

        data = array.array('B', data)
        status, _ = api.aa_i2c_write_ext(self.handle, i2c_address, flags, data)
        _raise_i2c_status_code_error_if_failure(status)

    def i2c_master_read(self, addr, length, flags=I2C_NO_FLAGS):
        """Make an I2C read access.

        The given I2C device is addressed and clock cycles for `length` bytes
        are generated. A short read will occur if the device generates an early
        NAK.

        The transaction is finished with an I2C stop condition unless the
        I2C_NO_STOP flag is set.
        """

        data = array.array('B', (0,) * length)
        status, data, rx_len = api.aa_i2c_read_ext(self.handle, addr,
                flags, data)
        _raise_i2c_status_code_error_if_failure(status)
        del data[rx_len:]
        return bytes(data)

    def i2c_master_write_read(self, i2c_address, data, length):
        """Make an I2C write/read access.

        First an I2C write access is issued. No stop condition will be
        generated. Instead the read access begins with a repeated start.

        This method is useful for accessing most addressable I2C devices like
        EEPROMs, port expander, etc.

        Basically, this is just a convenient function which internally uses
        `i2c_master_write` and `i2c_master_read`.
        """

        self.i2c_master_write(i2c_address, data, I2C_NO_STOP)
        return self.i2c_master_read(i2c_address, length)

    def poll(self, timeout=None):
        """Wait for an event to occur.

        If `timeout` is given, if specifies the length of time in milliseconds
        which the function will wait for events before returing. If `timeout`
        is omitted, negative or None, the call will block until there is an
        event.

        Returns a list of events. In case no event is pending, an empty list is
        returned.
        """
        if timeout is None:
            timeout = -1

        ret = api.aa_async_poll(self.handle, timeout)
        _raise_error_if_negative(ret)

        events = list()
        for event in (POLL_I2C_READ, POLL_I2C_WRITE, POLL_SPI,
                POLL_I2C_MONITOR):
            if ret & event:
                events.append(event)
        return events

    def enable_i2c_slave(self, slave_address):
        """Enable I2C slave mode.

        The device will respond to the specified slave_address if it is
        addressed.

        You can wait for the data with :func:`poll` and get it with
        `i2c_slave_read`.
        """
        ret = api.aa_i2c_slave_enable(self.handle, slave_address,
                self.BUFFER_SIZE, self.BUFFER_SIZE)
        _raise_error_if_negative(ret)

    def disable_i2c_slave(self):
        """Disable I2C slave mode."""
        ret = api.aa_i2c_slave_disable(self.handle)
        _raise_error_if_negative(ret)

    def i2c_slave_read(self):
        """Read the bytes from an I2C slave reception.

        The bytes are returned as a string object.
        """
        data = array.array('B', (0,) * self.BUFFER_SIZE)
        status, addr, rx_len = api.aa_i2c_slave_read_ext(self.handle, data)
        _raise_i2c_status_code_error_if_failure(status)

        # In case of general call, actually return the general call address
        if addr == 0x80:
            addr = 0x00
        del data[rx_len:]
        return (addr, bytes(data))

    @property
    def i2c_slave_response(self):
        """Response to next read command.

        An array of bytes that will be transmitted to the I2C master with the
        next read operation.

        Warning: Due to the fact that the Aardvark API does not provide a means
        to read out this value, it is buffered when setting the property.
        Reading the property therefore might not return what is actually stored
        in the device.
        """
        return self._i2c_slave_response

    @i2c_slave_response.setter
    def i2c_slave_response(self, data):
        data = array.array('B', data)
        ret = api.aa_i2c_slave_set_response(self.handle, data)
        _raise_error_if_negative(ret)
        self._i2c_slave_response = data

    @property
    def i2c_slave_last_transmit_size(self):
        """Returns the number of bytes transmitted by the slave."""
        ret = api.aa_i2c_slave_write_stats(self.handle)
        _raise_error_if_negative(ret)
        return ret

    def enable_i2c_monitor(self):
        """Activate the I2C monitor.

        Enabling the monitor will disable all other functions of the adapter.

        Raises an :exc:`IOError` if the hardware adapter does not support
        monitor mode.
        """
        ret = api.aa_i2c_monitor_enable(self.handle)
        _raise_error_if_negative(ret)

    def disable_i2c_monitor(self):
        """Disable the I2C monitor.

        Raises an :exc:`IOError` if the hardware adapter does not support
        monitor mode.
        """
        ret = api.aa_i2c_monitor_disable(self.handle)
        _raise_error_if_negative(ret)

    def i2c_monitor_read(self):
        """Retrieved any data fetched by the monitor.

        This function has an integrated timeout mechanism. You should use
        :func:`poll` to determine if there is any data available.

        Returns a list of data bytes and special symbols. There are three
        special symbols: `I2C_MONITOR_NACK`, I2C_MONITOR_START and
        I2C_MONITOR_STOP.

        """
        data = array.array('H', (0,) * self.BUFFER_SIZE)
        ret = api.aa_i2c_monitor_read(self.handle, data)
        _raise_error_if_negative(ret)
        del data[ret:]
        return data.tolist()

    @property
    def spi_bitrate(self):
        """SPI bitrate in kHz. Not every bitrate is supported by the host
        adapter. Therefore, the actual bitrate may be less than the value which
        is set. The slowest bitrate supported is 125kHz. Any smaller value will
        be rounded up to 125kHz.

        The power-on default value is 1000 kHz.
        """
        ret = api.aa_spi_bitrate(self.handle, 0)
        _raise_error_if_negative(ret)
        return ret

    @spi_bitrate.setter
    def spi_bitrate(self, value):
        ret = api.aa_spi_bitrate(self.handle, value)
        _raise_error_if_negative(ret)

    def spi_configure(self, polarity, phase, bitorder):
        """Configure the SPI interface."""
        ret = api.aa_spi_configure(self.handle, polarity, phase, bitorder)
        _raise_error_if_negative(ret)

    def spi_configure_mode(self, spi_mode):
        """Configure the SPI interface by the well known SPI modes."""
        if spi_mode == SPI_MODE_0:
            self.spi_configure(SPI_POL_RISING_FALLING,
                    SPI_PHASE_SAMPLE_SETUP, SPI_BITORDER_MSB)
        elif spi_mode == SPI_MODE_3:
            self.spi_configure(SPI_POL_FALLING_RISING,
                    SPI_PHASE_SETUP_SAMPLE, SPI_BITORDER_MSB)
        else:
            raise RuntimeError('SPI Mode not supported')

    def spi_write(self, data):
        """Write a stream of bytes to a SPI device."""
        data_out = array.array('B', data)
        data_in = array.array('B', (0,) * len(data_out))
        ret, data_in = api.aa_spi_write(self.handle, data_out, data_in)
        _raise_error_if_negative(ret)
        return bytes(data_in)

    def spi_ss_polarity(self, polarity):
        """Change the ouput polarity on the SS line.

        Please note, that this only affects the master functions.
        """
        ret = api.aa_spi_master_ss_polarity(self.handle, polarity)
        _raise_error_if_negative(ret)

    @property
    def configured_gpio_outputs(self):
        """Configuration of GPIO pin directions.

        To configure pins as outputs, set this property to a list of `GPIO_*`
        bitmasks.

        Examples:
            aardvark_instance.configured_gpio_outputs = [GPIO_SDA]
            aardvark_instance.configured_gpio_outputs = [GPIO_SS, GPIO_SCK]
        """
        return self._configured_gpio_outputs

    @configured_gpio_outputs.setter
    def configured_gpio_outputs(self, used_outputs):
        bitmask = sum(used_outputs)
        if bitmask == sum(self._configured_gpio_outputs):
            return
        ret = api.aa_gpio_direction(self.handle, bitmask)
        _raise_error_if_negative(ret)
        self._configured_gpio_outputs = used_outputs

    @property
    def enabled_gpio_pullups(self):
        """GPIO pullup configuration.

        To enable pull-up resitors, set this property to a list of `GPIO_*`
        bitmasks.

        Examples:
            aardvark_instance.enabled_gpio_pullups = [GPIO_SCL]
            aardvark_instance.enabled_gpio_pullups = [GPIO_MOSI, GPIO_MISO]
        """
        return self._enabled_gpio_pullups

    @enabled_gpio_pullups.setter
    def enabled_gpio_pullups(self, enabled_pullups):
        bitmask = sum(enabled_pullups)
        if bitmask == sum(self._enabled_gpio_pullups):
            return
        ret = api.aa_gpio_pullup(self.handle, bitmask)
        _raise_error_if_negative(ret)
        self._enabled_gpio_pullups = enabled_pullups

    def gpio_clear(self, output):
        """Drive a given GPIO output low."""
        if not output in self._high_gpio_outputs:
            return
        new_list = list(self._high_gpio_outputs)
        new_list.remove(output)
        mask = sum(new_list)
        ret = api.aa_gpio_set(self.handle, mask)
        _raise_error_if_negative(ret)
        self._high_gpio_outputs = new_list

    def gpio_get(self, output):
        """Read the state of a GPIO pin.

        As the Aardvark library does not provide a way to read the state of a
        GPIO output, the state of every output is cached and read out from
        there.

        This function returns `True` if the pin is currently high.
        """
        if output in self._configured_gpio_outputs:
            return output in self._high_gpio_outputs
        # Not an ouptut pin => poll inputs
        return output in self.gpio_poll(32)

    def gpio_poll(self, timeout):
        """Blocks until a GPIO input change is detected.

        You must specify a maximum time in [ms], after which the function will
        return in case nothing changes.

        In any case, a list of GPIO inputs that are currently high is returned.
        """
        bitmask = api.aa_gpio_change(self.handle, timeout)
        _raise_error_if_negative(bitmask)
        gpios = [GPIO_MISO, GPIO_MOSI, GPIO_SCK, GPIO_SCL, GPIO_SDA, GPIO_SS]
        return [pin for pin in gpios if bitmask & pin != 0x00]

    def gpio_set(self, output):
        """Drive a given GPIO output high."""
        if output in self._high_gpio_outputs:
            return
        new_list = list(self._high_gpio_outputs)
        new_list.append(output)
        mask = sum(new_list)
        ret = api.aa_gpio_set(self.handle, mask)
        _raise_error_if_negative(ret)
        self._high_gpio_outputs = new_list

    def gpio_toggle(self, output):
        """Toggle a given GPIO output."""
        if output in self._high_gpio_outputs:
            self.gpio_clear(output)
        else:
            self.gpio_set(output)
