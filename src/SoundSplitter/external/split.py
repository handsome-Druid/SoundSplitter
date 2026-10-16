from fractions import Fraction
from logging import Logger, getLogger
from types import TracebackType
from typing import NamedTuple, Self, cast, override

from av import AudioFormat, AudioFrame, AudioLayout
from av.filter import Graph
from av.filter.context import FilterContext
from numpy import dtype, frombuffer, ndarray
from PySide6.QtCore import (
    QMutex,
    QObject,
    QThread,
    Signal,
    Slot,
)
from PySide6.QtMultimedia import QAudioDevice, QAudioFormat
from soundcard import get_microphone, get_speaker

from SoundSplitter.external import Config


class Split(QObject):
    finished = Signal(object, object, object)
    _logger: Logger = getLogger(name=__name__)

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
        channels: int = fmt.channelCount()
        bpf: int = fmt.bytesPerFrame()
        return Split._Format(rate, format, layout, channels, bpf)

    @override
    def __init__(
        self,
        config: Config,
        /,
    ) -> None:
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
        self._left_sink: FilterContext = graph.add(filter="abuffersink")
        self._right_sink: FilterContext = graph.add(filter="abuffersink")
        for index, (target, latency, sink) in enumerate(
            iterable=zip(
                (self._left_fmt, self._right_fmt),
                (self._config.left_latency_ms, self._config.right_latency_ms),
                (self._left_sink, self._right_sink),
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
            format.link_to(input_=sink)
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
            with (
                get_microphone(
                    id=bytes(
                        cast(QAudioDevice, self._source_device).id().data()
                    ).decode(),
                    include_loopback=True,
                ).recorder(
                    samplerate=self._source_fmt.rate,
                    blocksize=self._source_fmt.rate
                    * self._config.source_buffer_time_ms
                    // 1000,
                ) as recorder,
                get_speaker(
                    id=bytes(cast(QAudioDevice, self._left_device).id().data()).decode()
                ).player(
                    samplerate=self._left_fmt.rate,
                    channels=self._left_fmt.channels,
                    blocksize=self._left_fmt.rate
                    * self._config.left_buffer_time_ms
                    // 1000,
                ) as left_player,
                get_speaker(
                    id=bytes(
                        cast(QAudioDevice, self._right_device).id().data()
                    ).decode()
                ).player(
                    samplerate=self._right_fmt.rate,
                    channels=self._right_fmt.channels,
                    blocksize=self._right_fmt.rate
                    * self._config.right_buffer_time_ms
                    // 1000,
                ) as right_player,
            ):
                while not self.thread().isInterruptionRequested():
                    frame: AudioFrame = AudioFrame.from_ndarray(
                        array=recorder.record().reshape(1, -1),
                        format="flt",
                        layout=self._source_fmt.layout,
                    )
                    frame.sample_rate = self._source_fmt.rate
                    self._input.push(frame)
                    for format, player, sink in zip(
                        (self._left_fmt, self._right_fmt),
                        (left_player, right_player),
                        (self._left_sink, self._right_sink),
                    ):
                        while True:
                            try:
                                output: AudioFrame = cast(AudioFrame, sink.pull())
                            except BlockingIOError:
                                break
                            frames: ndarray[tuple[int, int], dtype] = frombuffer(
                                buffer=memoryview(output.planes[0])[
                                    : output.samples * format.bpf
                                ],
                                dtype="float32",
                            ).reshape(-1, format.channels)
                            player.play(
                                data=frames * self._config.gain
                                if self._config.gain != 1.0
                                else frames
                            )
            self._input.push(frame=None)
            for format, player, sink in zip(
                (self._left_fmt, self._right_fmt),
                (left_player, right_player),
                (self._left_sink, self._right_sink),
            ):
                while True:
                    try:
                        output: AudioFrame = cast(AudioFrame, sink.pull())
                    except BlockingIOError:
                        break
                    frames: ndarray[tuple[int, int], dtype] = frombuffer(
                        buffer=memoryview(output.planes[0])[
                            : output.samples * format.bpf
                        ],
                        dtype="float32",
                    ).reshape(-1, format.channels)
                    player.play(
                        data=frames * self._config.gain
                        if self._config.gain != 1.0
                        else frames
                    )
        except BaseException as e:
            self.__exit__(type(e), e, e.__traceback__)
            raise
