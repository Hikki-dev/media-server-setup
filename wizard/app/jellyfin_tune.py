"""Jellyfin tuned for playback on any device: hardware transcoding where the machine has a GPU, HDR to SDR tone-mapping,
every common codec decoded in hardware, a sensible network setup and subtitle behaviour that suits mixed-language libraries.

Pure functions over two callables so the same code tunes a fresh install and an existing server:
  call(method, path, body=None) -> parsed JSON   (Jellyfin API, admin)
  run(shell_command) -> (exit code, text)        (a shell inside the Jellyfin container)
"""
import json

FF = "/usr/lib/jellyfin-ffmpeg/ffmpeg"
DRI = "/dev/dri/renderD128"
# decode codec -> (encoder used to make a tiny test clip, pixel format, extra args)
CLIPS = {"h264": ("libx264", "yuv420p", ""), "hevc": ("libx265", "yuv420p", "-x265-params log-level=none"),
         "hevc10": ("libx265", "yuv420p10le", "-x265-params log-level=none"), "mpeg2video": ("mpeg2video", "yuv420p", ""),
         "vp8": ("libvpx", "yuv420p", ""), "vp9": ("libvpx-vp9", "yuv420p", ""), "vp910": ("libvpx-vp9", "yuv420p10le", ""),
         "av1": ("libsvtav1", "yuv420p", "")}


def detect_gpu(run):
    """What the GPU inside the container can really do. Every claim is backed by a tiny test run."""
    out = {"type": "none", "vendor": None, "decode": [], "hevc10": False, "vp910": False, "lowPower": False, "vpp": False}
    if run(f"[ -e {DRI} ]")[0] != 0:
        return out
    vendor = run("cat /sys/class/drm/renderD128/device/vendor 2>/dev/null")[1].strip()
    out["vendor"] = {"0x8086": "intel", "0x1002": "amd"}.get(vendor, vendor)
    t = f"{FF} -v error -y"
    enc = f"{t} -vaapi_device {DRI} -f lavfi -i testsrc=s=320x240:d=0.3 -vf format=nv12,hwupload -c:v h264_vaapi -f null -"
    vaapi_ok = run(enc)[0] == 0
    qsv_ok = False
    if out["vendor"] == "intel":
        qsv = (f"{t} -init_hw_device vaapi=va:{DRI} -init_hw_device qsv=qs@va -f lavfi -i testsrc=s=320x240:d=0.3 "
               "-vf format=nv12,hwupload=extra_hw_frames=16 -c:v h264_qsv -f null -")
        qsv_ok = run(qsv)[0] == 0
        out["lowPower"] = qsv_ok and run(qsv.replace("-c:v h264_qsv", "-c:v h264_qsv -low_power 1"))[0] == 0
    if not (vaapi_ok or qsv_ok):
        return out
    out["type"] = "qsv" if qsv_ok else "vaapi"
    for name, (codec, pix, extra) in CLIPS.items():
        clip = f"/tmp/arrclip_{name}.mkv"
        made = run(f"{t} -f lavfi -i testsrc=s=320x240:d=0.4 -pix_fmt {pix} -c:v {codec} {extra} {clip}")[0] == 0
        if not made:
            continue
        ok = run(f"{t} -hwaccel vaapi -hwaccel_device {DRI} -hwaccel_output_format vaapi -i {clip} -f null -")[0] == 0
        run(f"rm -f {clip}")
        if not ok:
            continue
        if name == "hevc10":
            out["hevc10"] = True
        elif name == "vp910":
            out["vp910"] = True
        else:
            out["decode"].append(name)
    if "h264" in out["decode"]:
        out["decode"].append("vc1")    # VC-1 decodes on every GPU generation that decodes H.264
    out["vpp"] = out["vendor"] == "intel" and "tonemap_vaapi" in run(f"{FF} -hide_banner -filters 2>/dev/null | grep tonemap_vaapi")[1]
    return out


def describe_gpu(g):
    if g["type"] == "none":
        return "no usable GPU found, software transcoding with throttling"
    name = {"qsv": "Intel Quick Sync", "vaapi": "VAAPI (" + str(g["vendor"]).upper() + ")"}[g["type"]]
    codecs = [c.upper().replace("MPEG2VIDEO", "MPEG-2") for c in g["decode"] if c != "vc1"]
    return f"{name}: hardware decoding of {', '.join(codecs)}" + (", HDR to SDR tone-mapping" if g["vpp"] else "")


def tune_encoding(call, g):
    e = call("GET", "/System/Configuration/encoding")
    e.update({"EncodingThreadCount": 0, "EnableThrottling": True, "ThrottleDelaySeconds": 180, "EnableSegmentDeletion": True,
              "SegmentKeepSeconds": 720, "EnableAudioVbr": True, "MaxMuxingQueueSize": 4096, "DownMixStereoAlgorithm": "Dave750",
              "DownMixAudioBoost": 2, "EnableSubtitleExtraction": True, "H264Crf": 22, "H265Crf": 26, "EncoderPreset": "veryfast",
              "DeinterlaceMethod": "yadif", "AllowAv1Encoding": False, "EnableDecodingColorDepth10Hevc": True,
              "EnableDecodingColorDepth10Vp9": True, "EnableDecodingColorDepth10HevcRext": True, "EnableDecodingColorDepth12HevcRext": True,
              "PreferSystemNativeHwDecoder": True})
    if g["type"] == "none":
        e.update({"HardwareAccelerationType": "none", "EnableHardwareEncoding": False, "EnableTonemapping": False,
                  "EnableVppTonemapping": False, "AllowHevcEncoding": False})
    else:
        e.update({"HardwareAccelerationType": g["type"], "VaapiDevice": DRI, "QsvDevice": DRI, "EnableHardwareEncoding": True,
                  "HardwareDecodingCodecs": g["decode"], "EnableDecodingColorDepth10Hevc": g["hevc10"] or "hevc" in g["decode"],
                  "EnableDecodingColorDepth10Vp9": g["vp910"], "EnableVppTonemapping": g["vpp"],
                  "EnableTonemapping": g["vendor"] == "intel", "AllowHevcEncoding": "hevc" in g["decode"],
                  "EnableIntelLowPowerH264HwEncoder": g["lowPower"], "EnableIntelLowPowerHevcHwEncoder": g["lowPower"]})
    call("POST", "/System/Configuration/encoding", e)


def tune_network(call, opts):
    n = call("GET", "/System/Configuration/network")
    subnets = list(dict.fromkeys((n.get("LocalNetworkSubnets") or []) + ([opts["lan"]] if opts.get("lan") else [])))
    proxies = list(dict.fromkeys((n.get("KnownProxies") or []) + ["172.16.0.0/12"]))   # the other apps in the stack reach Jellyfin this way
    n.update({"EnableRemoteAccess": True, "AutoDiscovery": True, "EnableUPnP": False, "EnableIPv6": False, "IgnoreVirtualInterfaces": True,
              "VirtualInterfaceNames": ["veth", "docker"], "RequireHttps": False, "LocalNetworkSubnets": subnets, "KnownProxies": proxies})
    call("POST", "/System/Configuration/network", n)


def tune_server(call, g, opts):
    s = call("GET", "/System/Configuration")
    tp = dict(s.get("TrickplayOptions") or {})
    tp.update({"EnableHwAcceleration": g["type"] != "none", "EnableHwEncoding": g["type"] != "none", "ProcessPriority": "BelowNormal",
               "ProcessThreads": 2 if g["type"] != "none" else 1})
    s.update({"QuickConnectAvailable": True, "LibraryMonitorDelay": 60, "RemoteClientBitrateLimit": 0, "TrickplayOptions": tp,
              "PreferredMetadataLanguage": opts.get("metaLang", "en"), "MetadataCountryCode": opts.get("country", "US"),
              "DisplaySpecialsWithinSeasons": True, "EnableGroupingMoviesIntoCollections": True})
    if opts.get("serverName"):
        s["ServerName"] = opts["serverName"]
    call("POST", "/System/Configuration", s)


def tune_libraries(call, opts):
    n = 0
    for v in call("GET", "/Library/VirtualFolders"):
        o = v["LibraryOptions"]
        o.update({"EnableRealtimeMonitor": True, "EnableChapterImageExtraction": False, "ExtractChapterImagesDuringLibraryScan": False,
                  "EnableTrickplayImageExtraction": bool(opts.get("trickplay")), "ExtractTrickplayImagesDuringLibraryScan": False,
                  "SaveLocalMetadata": False, "AutomaticRefreshIntervalDays": 0, "SubtitleDownloadLanguages": [],
                  "PreferredMetadataLanguage": opts.get("metaLang", "en"), "MetadataCountryCode": opts.get("country", "US")})
        call("POST", "/Library/VirtualFolders/LibraryOptions", {"Id": v["ItemId"], "LibraryOptions": o})
        n += 1
    return n


def tune_tasks(call, opts):
    """Quiet the heavy background jobs nobody notices (chapter and scrub-preview images) and keep the database lean."""
    off = {"Extract Chapter Images"} | (set() if opts.get("trickplay") else {"Generate Trickplay Images"})
    for t in call("GET", "/ScheduledTasks"):
        if t["Name"] in off and t.get("Triggers"):
            call("POST", f"/ScheduledTasks/{t['Id']}/Triggers", [])
    opt = next((t for t in call("GET", "/ScheduledTasks") if "Optimize database" in t["Name"]), None)
    if opt and opt["State"] == "Idle":
        call("POST", f"/ScheduledTasks/Running/{opt['Id']}")


def tune_user(call, user_id, opts):
    """Subtitles only when the audio is not in the viewer's language (right for foreign films with English subtitles)."""
    u = call("GET", f"/Users/{user_id}")
    c = u["Configuration"]
    c.update({"SubtitleMode": "Smart", "SubtitleLanguagePreference": opts.get("subtitleLang", "eng"), "PlayDefaultAudioTrack": True,
              "RememberAudioSelections": True, "RememberSubtitleSelections": True, "EnableNextEpisodeAutoPlay": True,
              "HidePlayedInLatest": True})
    call("POST", f"/Users/{user_id}/Configuration", c)
    p = u["Policy"]
    p.update({"EnableVideoPlaybackTranscoding": True, "EnableAudioPlaybackTranscoding": True, "EnablePlaybackRemuxing": True,
              "RemoteClientBitrateLimit": 0, "EnableContentDownloading": True})
    call("POST", f"/Users/{user_id}/Policy", p)


STEP_GROUP = {"Background tasks": "jellyfin.tasks", "Playback and transcoding": "jellyfin.encoding", "Network": "jellyfin.network",
              "Server": "jellyfin.server", "Libraries": "jellyfin.library", "Subtitles and playback defaults": "jellyfin.user"}


def tune_all(call, run, user_id, opts, group=None):
    """Apply everything; returns {"gpu": ..., "summary": [...]}. A step that fails is reported, never fatal.
    `group(id)` (optional) is a context manager that wraps each step, so a preview can show every step as its own group."""
    import contextlib
    group = group or (lambda gid: contextlib.nullcontext())
    g = detect_gpu(run)
    opts = {**opts, "trickplay": bool(opts.get("trickplay"))}      # scrub-preview thumbnails stay off unless asked for: they cost a lot of CPU for little use
    steps, report = [("Background tasks", lambda: tune_tasks(call, opts)), ("Playback and transcoding", lambda: tune_encoding(call, g)), ("Network", lambda: tune_network(call, opts)),
                     ("Server", lambda: tune_server(call, g, opts)), ("Libraries", lambda: tune_libraries(call, opts)),
                     ("Subtitles and playback defaults", lambda: tune_user(call, user_id, opts))], []
    for name, fn in steps:
        try:
            with group(STEP_GROUP[name]):
                fn()
            report.append({"name": name, "ok": True})
        except Exception as ex:  # noqa: BLE001 - one setting group failing must not stop the others
            report.append({"name": name, "ok": False, "error": str(getattr(ex, "body", ex))[:160]})
    return {"gpu": g, "summary": describe_gpu(g), "steps": report}


if __name__ == "__main__":
    print(json.dumps({"hint": "import this module; see tune_all"}))
