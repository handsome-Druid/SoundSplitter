from fractions import Fraction
from logging import Logger, getLogger
from types import TracebackType
from typing import NamedTuple, Self, cast, override

from av import AudioFormat, AudioFrame, AudioLayout
from av.filter import Graph
from av.filter.context import FilterContext
from PySide6.QtCore import (
    QCoreApplication,
    QEvent,
    QIODevice,
    QMutex,
    QObject,
    QThread,
    Signal,
    Slot,
)
from PySide6.QtMultimedia import QAudioDevice, QAudioFormat, QAudioSource, QtAudio
from shiboken6 import isValid
from soundcard import get_microphone


class Split(QObject):
    finished = Signal(object, object, object)
    _logger: Logger = getLogger(name=__name__)
    _mutex = QMutex()

    class _Format(NamedTuple):
        rate: int
        format: AudioFormat
        layout: AudioLayout
        bpf: int

    @staticmethod
    def _handler(
        fmt: QAudioFormat,
        /,
    ) -> Split._Format:
        rate: int = fmt.sampleRate()
        format: AudioFormat = AudioFormat(
            name=fmt.sampleFormat()
            .name.replace("UInt", "u")
            .replace("Int", "s")
            .replace("Float", "flt")
        )
        layout: AudioLayout = AudioLayout(
            layout=fmt.channelConfig()
            .name.removeprefix("ChannelConfig")
            .removeprefix("Surround")
            .replace("Dot", ".")
            .lower()
        )
        bpf: int = fmt.bytesPerFrame()
        return Split._Format(rate, format, layout, bpf)

    @override
    def __init__(
        self,
        /,
        left_io: QIODevice,
        right_io: QIODevice,
        left_fmt: QAudioFormat,
        right_fmt: QAudioFormat,
        source_device: QAudioDevice,
        left_latency: int = 0,
        right_latency: int = 0,
        source_buffer_time_ms: int = 250,
        source_native_period: int = -1,
    ) -> None:
        super().__init__()
        self._source_buffer_time_ms: int = source_buffer_time_ms
        self._source_native_period: int = source_native_period
        self._ios: list[QIODevice] = [left_io, right_io]
        self._source_device: QAudioDevice = source_device
        self._source_fmt: Split._Format = self._handler(source_device.preferredFormat())
        self._left_fmt: Split._Format = self._handler(left_fmt)
        self._right_fmt: Split._Format = self._handler(right_fmt)
        graph: Graph = Graph()
        self._input: FilterContext = graph.add_abuffer(
            sample_rate=self._source_fmt.rate,
            format=self._source_fmt.format
            if self._source_device.mode() == QAudioDevice.Mode.Input
            else "flt",
            layout=self._source_fmt.layout,
            time_base=Fraction(numerator=1, denominator=self._source_fmt.rate),
        )
        mix: FilterContext = graph.add(
            filter="aformat",
            sample_rates=str(object=self._source_fmt.rate),
            sample_fmts=self._source_fmt.format.planar.name
            if self._source_device.mode() == QAudioDevice.Mode.Input
            else "fltp",
            channel_layouts="stereo",
        )
        splitter: FilterContext = graph.add(
            filter="channelsplit", args="channel_layout=stereo"
        )
        self._input.link_to(input_=mix)
        mix.link_to(input_=splitter)
        self._sinks: tuple[FilterContext, FilterContext] = (
            graph.add(filter="abuffersink"),
            graph.add(filter="abuffersink"),
        )
        for index, (target, latency) in enumerate(
            iterable=zip(
                (self._left_fmt, self._right_fmt),
                (left_latency, right_latency),
                strict=True,
            )
        ):
            resample: FilterContext = graph.add(filter="aresample", ichl="mono")
            format: FilterContext = graph.add(
                filter="aformat",
                sample_rates=str(object=target.rate),
                sample_fmts=target.format.name,
                channel_layouts=target.layout.name,
            )
            if latency > 0:
                delay: FilterContext = graph.add(
                    filter="adelay",
                    delays=str(object=latency),
                    all="1",
                )
                splitter.link_to(input_=delay, output_idx=index, input_idx=0)
                delay.link_to(input_=resample)
            else:
                splitter.link_to(input_=resample, output_idx=index, input_idx=0)
            resample.link_to(input_=format)
            format.link_to(input_=self._sinks[index])
        graph.configure()

    def __enter__(self) -> Self:
        return self

    @Slot(object, object, object)
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
        /,
    ) -> None:
        is_running: bool = not self._mutex.try_lock()
        if hasattr(self, "_source") and isValid(self._source):
            self._source.stop()
            self._source.deleteLater()
            QCoreApplication.sendPostedEvents(
                receiver=self._source,
                event_type=QEvent.Type.DeferredDelete,
            )
        try:
            if hasattr(self, "_ios"):
                ios: list[QIODevice] = self._ios
                del self._ios
                self._input.push(frame=None)
                for index, target in enumerate(
                    iterable=(self._left_fmt, self._right_fmt)
                ):
                    while True:
                        try:
                            output: AudioFrame = cast(
                                AudioFrame, self._sinks[index].pull()
                            )
                        except EOFError:
                            break
                        ios[index].write(
                            bytes(
                                memoryview(output.planes[0])[
                                    : output.samples * target.bpf
                                ]
                            )
                        )
        finally:
            self._mutex.unlock()
            if is_running:
                self.finished.emit(exc_type, exc, tb)
            if not QThread.isMainThread():
                self.thread().quit()

    @Slot(object, object, object)
    def __call__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
        /,
    ) -> None:
        if exc_type is not None:
            self.__exit__(exc_type, exc, tb)
            return
        if not self._mutex.try_lock():
            return
        try:
            match self._source_device.mode():
                case QAudioDevice.Mode.Input:
                    self._source = QAudioSource(self._source_device)
                    self._source.setBufferFrameCount(
                        self._source_fmt.rate * self._source_buffer_time_ms // 1000
                    )
                    self._source.setNativePeriodFrameCount(self._source_native_period)
                    self._source.stateChanged.connect(self._on_state_changed)
                    self._source_io: QIODevice = self._source.start()
                    self._source_io.readyRead.connect(self._on_ready_read)
                case QAudioDevice.Mode.Output:
                    with get_microphone(
                        id=bytes(self._source_device.id().data()).decode(),
                        include_loopback=True,
                    ).recorder(samplerate=self._source_fmt.rate) as recorder:
                        while True:
                            if self.thread().isInterruptionRequested():
                                break
                            frame: AudioFrame = AudioFrame.from_ndarray(
                                array=recorder.record().reshape(1, -1),
                                format="flt",
                                layout=self._source_fmt.layout,
                            )
                            frame.sample_rate = self._source_fmt.rate
                            self._input.push(frame)
                            for index, target in enumerate(
                                iterable=(self._left_fmt, self._right_fmt)
                            ):
                                while True:
                                    try:
                                        output: AudioFrame = cast(
                                            AudioFrame, self._sinks[index].pull()
                                        )
                                    except BlockingIOError:
                                        break
                                    payload: bytes = bytes(
                                        memoryview(output.planes[0])[
                                            : output.samples * target.bpf
                                        ]
                                    )
                                    written: int = self._ios[index].write(payload)
                                    if written != len(payload):
                                        self._logger.warning(
                                            msg=(
                                                self.tr("Left channel output")
                                                if index == 0
                                                else self.tr("Right channel output")
                                            )
                                            + self.tr(" audio short write: ")
                                            + str(object=written)
                                            + " / "
                                            + str(object=len(payload))
                                            + self.tr(" bytes")
                                        )
                case _:
                    raise RuntimeError(
                        self.tr("Selected source device is unavailable!")
                    )
        except BaseException as e:
            self.__exit__(type(e), e, e.__traceback__)
            raise

    @Slot()
    def _on_ready_read(self) -> None:
        try:
            data: bytes = cast(bytes, self._source_io.readAll())
            if not data:
                return
            frame: AudioFrame = AudioFrame(
                format=self._source_fmt.format,
                layout=self._source_fmt.layout,
                samples=len(data) // self._source_fmt.bpf,
            )
            frame.sample_rate = self._source_fmt.rate
            memoryview(frame.planes[0])[:] = memoryview(data)
            self._input.push(frame)
            for index, target in enumerate(iterable=(self._left_fmt, self._right_fmt)):
                while True:
                    try:
                        output: AudioFrame = cast(AudioFrame, self._sinks[index].pull())
                    except BlockingIOError:
                        break
                    payload: bytes = bytes(
                        memoryview(output.planes[0])[: output.samples * target.bpf]
                    )
                    written: int = self._ios[index].write(payload)
                    if written != len(payload):
                        self._logger.warning(
                            msg=(
                                self.tr("Left channel output")
                                if index == 0
                                else self.tr("Right channel output")
                            )
                            + self.tr(" audio short write: ")
                            + str(object=written)
                            + " / "
                            + str(object=len(payload))
                            + self.tr(" bytes")
                        )
        except BaseException as e:
            self.__exit__(type(e), e, e.__traceback__)
            raise

    @Slot()
    def _on_state_changed(self) -> None:
        if self._source.state() == QtAudio.State.IdleState:
            self._logger.warning(
                msg=self.tr(
                    "The input source buffer is full; audio data has been discarded"
                )
            )
