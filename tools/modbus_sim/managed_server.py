#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Provides a managed Modbus RTU server for tools and interactive demos."""

import asyncio
import threading

from pymodbus import FramerType
from pymodbus.server import ModbusSerialServer


class ManagedModbusServer:
    """Runs one serial server and exposes thread-safe register access."""

    def __init__(self, context, unit_id, serial_config):
        self.context = context
        self.unit_id = unit_id
        self.serial_config = {
            "port": serial_config["port"],
            "baudrate": serial_config["baudrate"],
            "bytesize": 8,
            "parity": serial_config.get("parity", "N"),
            "stopbits": serial_config.get("stopbits", 1),
        }
        self.loop = None
        self.server = None
        self.thread = None
        self.ready = threading.Event()
        self.error = None

    def start(self):
        """Starts the server thread and waits until the serial port is bound."""
        if self.thread is not None:
            raise RuntimeError("Modbus server has already been started")
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run, name="modbus-rtu-server")
        self.thread.start()
        if not self.ready.wait(5):
            self.stop()
            raise TimeoutError("Modbus 从站启动超过 5 秒")
        if self.error is not None:
            raise RuntimeError("Modbus 从站启动失败：{}".format(self.error))

    def _run(self):
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self._serve())
        except Exception as error:
            self.error = error
            self.ready.set()
        finally:
            if not self.loop.is_closed():
                self.loop.close()

    async def _serve(self):
        self.server = ModbusSerialServer(
            self.context,
            framer=FramerType.RTU,
            **self.serial_config
        )
        await self.server.serve_forever(background=True)
        self.ready.set()
        await self.server.serving

    def _call_on_loop(self, operation, timeout=2):
        """Runs one datastore operation on the server event-loop thread."""
        if self.loop is None or self.thread is None or not self.thread.is_alive():
            raise RuntimeError("Modbus server is not running")
        completed = threading.Event()
        result = []

        def invoke():
            try:
                result.append(operation(self.context[self.unit_id]))
            except Exception as error:
                result.append(error)
            finally:
                completed.set()

        self.loop.call_soon_threadsafe(invoke)
        if not completed.wait(timeout):
            raise TimeoutError("Modbus 寄存器操作超时")
        if isinstance(result[0], Exception):
            raise RuntimeError("Modbus 寄存器操作失败：{}".format(result[0]))
        return result[0]

    def get_registers(self, address, count):
        """Returns holding-register values from the active slave context."""
        return self._call_on_loop(
            lambda slave: slave.getValues(3, address, count=count)
        )

    def set_registers(self, address, values):
        """Updates holding registers without stopping the serial server."""
        self._call_on_loop(lambda slave: slave.setValues(3, address, values))

    def stop(self):
        """Stops the server and joins its thread; safe to call more than once."""
        if self.loop is None or self.thread is None or not self.thread.is_alive():
            return
        if self.server is not None:
            future = asyncio.run_coroutine_threadsafe(self.server.shutdown(), self.loop)
            try:
                future.result(timeout=3)
            except Exception:
                self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(timeout=3)
        if self.thread.is_alive():
            self.loop.call_soon_threadsafe(self.loop.stop)
            self.thread.join(timeout=2)
