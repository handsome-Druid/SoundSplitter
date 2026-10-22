from collections.abc import Mapping
from fractions import Fraction
from logging import Logger, getLogger
from types import TracebackType
from typing import ClassVar, NamedTuple, Self, cast, override

from av import AudioFormat, AudioFrame, AudioLayout
from av.filter import Graph
from av.filter.context import FilterContext
from pyaudio import (  # pyright: ignore[reportMissingModuleSource]
    PyAudio,
    Stream,
    paContinue,
    paFloat32,
    paInputOverflow,
    paInputUnderflow,
    paInt16,
    paInt32,
    paJACK,
    paUInt8,
)
from PySide6.QtCore import (
    QIODevice,
    QMutex,
    QObject,
    Signal,
    Slot,
)
from PySide6.QtMultimedia import QAudioDevice, QAudioFormat, QAudioSink

from SoundSplitter.common import Config


class Split(QObject):
    finished = Signal(object, object, object)
    _logger: Logger = getLogger(name=__name__)
    _ready_read = Signal(object, int, dict, int)
    volume = Signal(float)

    class _Format(NamedTuple):
        rate: int
        format: AudioFormat
        layout: AudioLayout
        channels: int
        bpf: int
        pa_format: int

    _pa_format: ClassVar[dict[QAudioFormat.SampleFormat, int]] = {
        QAudioFormat.SampleFormat.Float: paFloat32,
        QAudioFormat.SampleFormat.Int16: paInt16,
        QAudioFormat.SampleFormat.Int32: paInt32,
        QAudioFormat.SampleFormat.UInt8: paUInt8,
    }

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
        pa_format: int = Split._pa_format[sample_format]
        return Split._Format(rate, format, layout, channels, bpf, pa_format)

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
            self._left_fmt: Split._Format = self._handler(
                self._left_device.preferredFormat()
            )
            self._right_fmt: Split._Format = self._handler(
                self._right_device.preferredFormat()
            )
            self._pyaudio = PyAudio()
            host_api_index: str | int = self._pyaudio.get_host_api_info_by_type(
                host_api_type=paJACK
            )["index"]
            source_name: str = self._source_device.description().translate(
                str.maketrans(" ()[].:*$", "_" * 9)
            )
            self._source_format: QAudioFormat = self._source_device.preferredFormat()
            for i in range(self._pyaudio.get_device_count()):
                device_info: Mapping[str, str | int | float] = (
                    self._pyaudio.get_device_info_by_index(device_index=i)
                )
                if device_info["hostApi"] != host_api_index:
                    continue
                if device_info["name"] == source_name:
                    self._source_index: int = i
                    self._source_format.setSampleRate(
                        int(device_info["defaultSampleRate"])
                    )
                    break
            self._source_fmt: Split._Format = self._handler(self._source_format)
            self._pts = 0
            self._debts: list[float] = [0.0, 0.0]
            self._left_target: int = (
                self._left_fmt.rate * (self._config.left_latency_ms + 10) // 1000
            )
            self._right_target: int = (
                self._right_fmt.rate * (self._config.right_latency_ms + 10) // 1000
            )
            self._ready_read.connect(self._on_ready_read)
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
                delay.link_to(input_=volume)
                volume.link_to(input_=format)
                format.link_to(input_=sink)
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
                    self._sink.stop()
                    del self._sink
                if hasattr(self, "_sink_io"):
                    del self._sink_io
                try:
                    if hasattr(self, "_source_stream"):
                        self._source_stream.stop_stream()
                        self._source_stream.close()
                        del self._source_stream
                finally:
                    try:
                        if hasattr(self, "_left_stream"):
                            self._left_stream.stop()
                            del self._left_stream
                            del self._left_io
                    finally:
                        if hasattr(self, "_right_stream"):
                            self._right_stream.stop()
                            del self._right_stream
                            del self._right_io
            finally:
                if hasattr(self, "_pyaudio"):
                    self._pyaudio.terminate()
                    del self._pyaudio
        finally:
            self._mutex.unlock()
            if not self.thread().isMainThread():
                self.thread().quit()
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
            if not hasattr(self, "_pyaudio"):
                self._pyaudio = PyAudio()
            assert self._source_device is not None
            assert self._left_device is not None
            assert self._right_device is not None
            self._left_stream = QAudioSink(self._left_device)
            self._right_stream = QAudioSink(self._right_device)
            if 10 + self._config.left_latency_ms > 125:
                self._left_stream.setBufferFrameCount(self._left_target * 2)
            if 10 + self._config.right_latency_ms > 125:
                self._right_stream.setBufferFrameCount(self._right_target * 2)
            self._source_stream: Stream = self._pyaudio.open(
                format=self._source_fmt.pa_format,
                channels=self._source_fmt.channels,
                rate=self._source_fmt.rate,
                input=True,
                input_device_index=self._source_index,
                start=False,
                stream_callback=lambda data, frame_count, time_info, status: (
                    self._ready_read.emit(data, frame_count, time_info, status),
                    None,
                    paContinue,
                )[-2:],
                frames_per_buffer=(
                    (
                        10
                        + min(
                            self._config.left_latency_ms,
                            self._config.right_latency_ms,
                        )
                    )
                    * self._source_fmt.rate
                    * 2
                    + 2999
                )
                // 3000,
            )
            if self._source_device.mode() == self._source_device.Mode.Output:
                sink_device: QAudioDevice | None = self._source_device
            else:
                sink_device = self._config.volume_device
            if sink_device is not None:
                self._sink = QAudioSink(sink_device, format=self._source_format)
                self._sink_io: QIODevice = self._sink.start()
                if self._sink_io is None:
                    self._logger.warning(
                        self.tr("Failed to start audio sink on device '%s'."),
                        sink_device.description(),
                    )
                    del self._sink_io
                else:
                    self._silent_chunk: bytes = (
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
            self._source_stream.start_stream()
        except BaseException as e:
            self.__exit__(type(e), e, e.__traceback__)
            raise

    @Slot(object, int, dict, int)
    def _on_ready_read(
        self,
        data: bytes | None,
        frame_count: int,
        time_info: Mapping[str, float],
        status: int,
    ) -> None:
        if data is None:
            return
        try:
            frame: AudioFrame = AudioFrame(
                format=self._source_fmt.format,
                layout=self._source_fmt.layout,
                samples=frame_count,
            )
            frame.sample_rate = self._source_fmt.rate
            frame.pts = self._pts
            self._pts += frame_count
            memoryview(frame.planes[0])[:] = data
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
                    payload = bytes(
                        memoryview(output.planes[0])[: output.samples * format.bpf],
                    )
                    written = io.write(payload)
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
                self._pts_filters[index].process_command(
                    cmd="expr", arg=f"PTS+{round(number=self._debts[index])}"
                )
            if status & paInputOverflow:
                self._logger.warning(
                    msg=self.tr("Capture overflow, samples discarded.")
                )
            if status & paInputUnderflow:
                self._logger.warning(
                    msg=self.tr("Capture underflow, silence inserted.")
                )
            if hasattr(self, "_sink_io"):
                self._sink_io.write(self._silent_chunk)
        except BaseException as e:
            self.__exit__(type(e), e, e.__traceback__)
            raise
