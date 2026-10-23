# Package a Nuitka standalone build without modifying its binaries.
%global debug_package %{nil}
%global __brp_strip %{nil}
%global __brp_strip_static_archive %{nil}
%global __brp_strip_comment_note %{nil}
%global _build_id_links none

Name:           soundsplitter
Version:        %{app_version}
Release:        1%{?dist}
Summary:        Split stereo audio between two output devices
License:        BSD-3-Clause
URL:            https://github.com/handsome-Druid/SoundSplitter

BuildRequires:  binutils
BuildRequires:  systemd-rpm-macros
Requires:       pipewire
Requires:       pipewire-jack-audio-connection-kit
Requires:       /usr/bin/pw-jack
Requires:       pipewire-pulseaudio
Requires:       wireplumber
Requires:       portaudio%{?_isa}
Requires:       pulseaudio-libs%{?_isa}
# Qt loads these libraries dynamically, outside ELF dependency discovery.
Requires:       xcb-util-cursor%{?_isa}
Requires:       mesa-libEGL%{?_isa}
Requires:       mesa-libGL%{?_isa}
Requires(post): /usr/bin/systemd-tmpfiles

%description
SoundSplitter routes left and right audio channels to separate devices,
with independent delay adjustment and volume monitoring.
This package contains a precompiled Nuitka standalone application.

%install
readelf -h "%{_sourcedir}/build/SoundSplitter.dist/SoundSplitter.bin" > /dev/null
install -d %{buildroot}%{_libdir}/SoundSplitter
cp -a "%{_sourcedir}/build/SoundSplitter.dist/." %{buildroot}%{_libdir}/SoundSplitter/
chmod 0755 %{buildroot}%{_libdir}/SoundSplitter/SoundSplitter.bin
install -Dpm 0755 "%{_sourcedir}/rpm/soundsplitter-launcher" %{buildroot}%{_bindir}/soundsplitter
sed -i 's|@LIBDIR@|%{_libdir}|g' %{buildroot}%{_bindir}/soundsplitter
install -Dpm 0644 "%{_sourcedir}/rpm/soundsplitter.desktop" %{buildroot}%{_datadir}/applications/soundsplitter.desktop
install -Dpm 0644 "%{_sourcedir}/rpm/io.github.handsome_druid.SoundSplitter.metainfo.xml" %{buildroot}%{_datadir}/metainfo/io.github.handsome_druid.SoundSplitter.metainfo.xml
install -Dpm 0644 "%{_sourcedir}/src/SoundSplitter/integration/app/resources/SS_headphones_solid_cute.svg" %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/soundsplitter.svg
install -Dpm 0644 "%{_sourcedir}/rpm/soundsplitter.tmpfiles" %{buildroot}%{_tmpfilesdir}/soundsplitter.conf
install -Dpm 0644 "%{_sourcedir}/rpm/copyright" %{buildroot}%{_licensedir}/%{name}/copyright

%post
%tmpfiles_create soundsplitter.conf

%files
%dir %{_licensedir}/%{name}
%license %{_licensedir}/%{name}/copyright
%{_libdir}/SoundSplitter/
%{_bindir}/soundsplitter
%{_datadir}/applications/soundsplitter.desktop
%{_datadir}/metainfo/io.github.handsome_druid.SoundSplitter.metainfo.xml
%{_datadir}/icons/hicolor/scalable/apps/soundsplitter.svg
%{_tmpfilesdir}/soundsplitter.conf
%ghost %dir %attr(1777,root,root) %{_sharedstatedir}/SoundSplitter
%ghost %dir %attr(1777,root,root) /run/SoundSplitter
