from fractions import Fraction
from logging import Logger, getLogger
from types import TracebackType
from typing import NamedTuple, Self, cast, override

from av import AudioFormat, AudioFrame, AudioLayout
from av.filter import Graph
from av.filter.context import FilterContext
from PySide6.QtCore import (
    QIODevice,
    QMetaObject,
    QMutex,
    QObject,
    QThread,
    Signal,
    Slot,
)
from PySide6.QtMultimedia import QAudioDevice, QAudioFormat, QAudioSink, QAudioSource

from SoundSplitter.common import Config


class Split(QObject):
    finished = Signal(object, object, object)
    _logger: Logger = getLogger(name=__name__)
    volume = Signal(float)

    class _Format(NamedTuple):
        rate: int
        format: AudioFormat
        layout: AudioLayout
        channels: int
        bpf: int

    @staticmethod
    def _handler(
        fmt: QAudioFormat,
        /,
    ) -> Split._Format:
        rate: int = fmt.sampleRate()
        sample_format: QAudioFormat.SampleFormat = fmt.sampleFormat()
        format: AudioFormat = AudioFormat(
            name=sample_format.name.replace("UInt", "u")
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
        channels: int = fmt.channelCount()
        bpf: int = fmt.bytesPerFrame()
        return Split._Format(rate, format, layout, channels, bpf)

    @override
    def __init__(
        self,
        config: Config,
        /,
    ) -> None:
        try:
            super().__init__()
            self._mutex = QMutex()
            self._config: Config = config
            self._left_device: QAudioDevice | None = self._config.left_device
            self._right_device: QAudioDevice | None = self._config.right_device
            self._source_device: QAudioDevice | None = self._config.source_device
            if self._left_device is None:
                raise RuntimeError(self.tr("No left channel output selected"))
            if self._right_device is None:
                raise RuntimeError(self.tr("No right channel output selected"))
            if self._source_device is None:
                raise RuntimeError(self.tr("No audio input source selected"))
            if self._left_device == self._right_device:
                raise RuntimeError(
                    self.tr("Left and right channel outputs cannot use the same device")
                )
            self._source_fmt: Split._Format = self._handler(
                self._source_device.preferredFormat()
            )
            self._left_fmt: Split._Format = self._handler(
                self._left_device.preferredFormat()
            )
            self._right_fmt: Split._Format = self._handler(
                self._right_device.preferredFormat()
            )
            self._pts = 0
            self._debts: list[float] = [0.0, 0.0]
            graph: Graph = Graph()
            self._input: FilterContext = graph.add_abuffer(
                sample_rate=self._source_fmt.rate,
                format=self._source_fmt.format,
                layout=self._source_fmt.layout,
                time_base=Fraction(numerator=1, denominator=self._source_fmt.rate),
            )
            mix: FilterContext = graph.add(
                filter="aformat",
                sample_rates=str(object=self._source_fmt.rate),
                sample_fmts=self._source_fmt.format.planar.name,
                channel_layouts="stereo",
            )
            splitter: FilterContext = graph.add(
                filter="channelsplit", args="channel_layout=stereo"
            )
            self._input.link_to(input_=mix)
            mix.link_to(input_=splitter)
            self._left_sink: FilterContext = graph.add(filter="abuffersink")
            self._right_sink: FilterContext = graph.add(filter="abuffersink")
            self._pts_filters: list[FilterContext] = []
            self._left_target: int = (
                self._left_fmt.rate * (self._config.left_latency_ms + 10) // 1000
            )
            self._right_target: int = (
                self._right_fmt.rate * (self._config.right_latency_ms + 10) // 1000
            )
            for index, (fmt, sink, target) in enumerate(
                iterable=zip(
                    (self._left_fmt, self._right_fmt),
                    (self._left_sink, self._right_sink),
                    (
                        self._left_target,
                        self._right_target,
                    ),
                )
            ):
                pts: FilterContext = graph.add(filter="asetpts", expr="PTS")
                resample: FilterContext = graph.add(
                    filter="aresample",
                    args=(
                        "ichl=mono:first_pts=0:min_hard_comp="
                        f"{target / fmt.rate / 2}"
                        ":async="
                        f"{target * self._source_fmt.rate / fmt.rate}"
                    ),
                )
                delay: FilterContext = graph.add(
                    filter="adelay",
                    delays=f"{target}S",
                    all="1",
                )
                format: FilterContext = graph.add(
                    filter="aformat",
                    sample_rates=str(object=fmt.rate),
                    sample_fmts=fmt.format.name,
                    channel_layouts=fmt.layout.name,
                )
                splitter.link_to(input_=pts, output_idx=index, input_idx=0)
                pts.link_to(input_=resample)
                self._pts_filters.append(pts)
                volume: FilterContext = graph.add(filter="volume")
                resample.link_to(input_=delay)
                delay.link_to(input_=format)
                format.link_to(input_=volume)
                volume.link_to(input_=sink)
                self.volume.connect(
                    lambda gain, volume=volume: volume.process_command(
                        cmd="volume", arg=str(object=gain)
                    )
                )
            graph.configure()
        except BaseException as e:
            self.__exit__(type(e), e, e.__traceback__)
            raise

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
        try:
            try:
                if hasattr(self, "_sink"):
                    QMetaObject.invokeMethod(self._sink, "stop")
                    del self._sink
                    del self._sink_io
            finally:
                try:
                    if hasattr(self, "_source_stream"):
                        QMetaObject.invokeMethod(self._source_stream, "stop")
                        del self._source_stream
                        del self._source_io
                finally:
                    try:
                        if hasattr(self, "_left_stream"):
                            QMetaObject.invokeMethod(self._left_stream, "stop")
                            del self._left_stream
                            del self._left_io
                    finally:
                        if hasattr(self, "_right_stream"):
                            QMetaObject.invokeMethod(self._right_stream, "stop")
                            del self._right_stream
                            del self._right_io
        finally:
            self._mutex.unlock()
            thread: QThread = self.thread()
            if thread == thread.currentThread():
                thread.quit()
            if is_running:
                self.finished.emit(exc_type, exc, tb)

    @Slot(object, object, object)
    def __call__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
        /,
    ) -> None:
        try:
            if exc_type is not None:
                self.__exit__(exc_type, exc, tb)
                return
            if not self._mutex.try_lock():
                return
            assert self._source_device is not None
            assert self._left_device is not None
            assert self._right_device is not None
            self._left_stream = QAudioSink(self._left_device)
            self._right_stream = QAudioSink(self._right_device)
            self._source_stream = QAudioSource(self._source_device)
            if self._config.left_latency_ms + 10 > 125:
                self._left_stream.setBufferFrameCount(self._left_target * 2)
            if self._config.right_latency_ms + 10 > 125:
                self._right_stream.setBufferFrameCount(self._right_target * 2)
            sink_device: QAudioDevice | None = self._config.volume_device
            if sink_device is not None:
                self._sink = QAudioSink(sink_device)
                self._sink_io: QIODevice = self._sink.start()
                if self._sink_io is None:
                    self._logger.warning(
                        self.tr("Failed to start audio sink on device '%s'."),
                        sink_device.description(),
                    )
                    del self._sink_io
                else:
                    self._silent_chunk = (
                        b"\x80" * self._sink.bufferSize()
                        if self._sink.format().sampleFormat()
                        == QAudioFormat.SampleFormat.UInt8
                        else bytes(self._sink.bufferSize())
                    )
                    self._sink_io.write(self._silent_chunk)
            self._left_io: QIODevice = self._left_stream.start()
            self._right_io: QIODevice = self._right_stream.start()
            self._left_capacity: int = self._left_stream.bufferSize()
            self._right_capacity: int = self._right_stream.bufferSize()
            self._source_io: QIODevice = self._source_stream.start()
            self._source_io.readyRead.connect(self._on_ready_read)
        except BaseException as e:
            self.__exit__(type(e), e, e.__traceback__)
            raise

    @Slot()
    def _on_ready_read(
        self,
    ) -> None:
        data: bytes = cast(bytes, self._source_io.readAll())
        if not data:
            return
        try:
            frame_count: int = len(data) // self._source_fmt.bpf
            frame: AudioFrame = AudioFrame(
                format=self._source_fmt.format,
                layout=self._source_fmt.layout,
                samples=frame_count,
            )
            frame.sample_rate = self._source_fmt.rate
            frame.pts = self._pts
            self._pts += frame_count
            memoryview(frame.planes[0])[:] = memoryview(data)
            self._input.push(frame=frame)
            for index, (format, stream, sink, capacity, target, io) in enumerate(
                iterable=zip(
                    (self._left_fmt, self._right_fmt),
                    (self._left_stream, self._right_stream),
                    (self._left_sink, self._right_sink),
                    (self._left_capacity, self._right_capacity),
                    (self._left_target, self._right_target),
                    (self._left_io, self._right_io),
                )
            ):
                backlog: int = (capacity - stream.bytesFree()) // format.bpf
                self._debts[index] += (
                    (target - backlog) * self._source_fmt.rate / format.rate * 0.01
                )
                while True:
                    try:
                        output: AudioFrame = cast(AudioFrame, sink.pull())
                    except BlockingIOError:
                        break
                    io.write(
                        bytes(
                            memoryview(output.planes[0])[: output.samples * format.bpf],
                        )
                    )
                self._pts_filters[index].process_command(
                    cmd="expr", arg=f"PTS+{round(number=self._debts[index])}"
                )
            if hasattr(self, "_sink_io"):
                self._sink_io.write(self._silent_chunk)
        except BaseException as e:
            self.__exit__(type(e), e, e.__traceback__)
            raise
