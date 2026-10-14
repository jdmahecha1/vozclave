"""Command line interface: `vozclave init | download-model | check | devices | enroll | run`."""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
from pathlib import Path

from vozclave import __version__, paths
from vozclave.config import Config, ConfigError, load

log = logging.getLogger("vozclave")
EXAMPLE_CONFIG = Path(__file__).parent / "example_config.toml"


def _load(args) -> Config:
    path = Path(args.config) if args.config else paths.default_config_path()
    config = load(path)
    log.debug("using config %s", path)
    return config


def _listen(config: Config):
    """Yield utterances from the microphone, restricted to the configured phrases."""
    from vozclave import listener
    from vozclave.matcher import Matcher

    matcher = Matcher(config.commands)
    model = listener.load_model(config.model)
    recognizer = listener.make_recognizer(model, matcher.grammar(), config.sample_rate)
    blocks = listener.microphone_blocks(config.sample_rate, config.input_device)
    return matcher, listener.utterances(recognizer, blocks, config.sample_rate)


def cmd_init(args) -> int:
    target = Path(args.config) if args.config else paths.home() / "config.toml"
    if target.exists() and not args.force:
        print(f"{target} already exists (use --force to overwrite)")
        return 1
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(EXAMPLE_CONFIG, target)
    print(f"Created {target}\nEdit your commands there, then run `vozclave check`.")
    return 0


def cmd_download_model(args) -> int:
    from vozclave import models

    path = models.download(args.lang, paths.models_dir())
    print(f"Model ready at {path}")
    return 0


def cmd_check(args) -> int:
    from vozclave import listener
    from vozclave.matcher import Matcher

    config = _load(args)
    matcher = Matcher(config.commands)  # also catches duplicated phrases
    print(f"{len(config.commands)} command(s), {len(matcher.grammar()) - 1} phrase(s)")

    problems = 0
    model = listener.load_model(config.model)
    missing = listener.unknown_words(model, matcher.words())
    if missing:
        problems += 1
        print("These words are not in the speech model, phrases using them will never match:")
        for word in missing:
            print(f"  - {word}")
    if config.sound.file and not config.sound.file.exists():
        problems += 1
        print(f"Sound file not found: {config.sound.file}")
    if config.voice.enabled and not paths.voiceprint_path().exists():
        problems += 1
        print("Voice verification is enabled but there is no voiceprint yet: run `vozclave enroll`")

    print("All good." if not problems else f"{problems} problem(s) found.")
    return 0 if not problems else 1


def cmd_devices(args) -> int:
    import sounddevice as sd

    apis = [api["name"] for api in sd.query_hostapis()]
    default_input = sd.default.device[0]
    for i, dev in enumerate(sd.query_devices()):
        if dev["max_input_channels"] > 0:
            mark = "*" if i == default_input else " "
            print(f"{mark}{i:>3}  {dev['name']}  ({apis[dev['hostapi']]})")
    print("\n* = default microphone")
    return 0


def cmd_enroll(args) -> int:
    from vozclave import speaker

    config = _load(args)
    print("Loading voice model...", flush=True)
    embed = speaker.ecapa_embedder(paths.models_dir())
    matcher, stream = _listen(config)

    print(
        f"Say any of your command phrases {args.samples} times, naturally. Ctrl+C to cancel.\n",
        flush=True,
    )
    samples = []
    for utt in stream:
        if matcher.match(utt.text) is None:
            continue
        samples.append(utt.audio)
        print(f"  [{len(samples)}/{args.samples}] heard: {utt.text}", flush=True)
        if len(samples) == args.samples:
            break

    voiceprint, consistency = speaker.build_voiceprint(embed, samples, config.sample_rate)
    speaker.save_voiceprint(paths.voiceprint_path(), voiceprint)
    print("\nHow consistent each sample is with the rest (higher is better):")
    for i, score in enumerate(consistency, 1):
        flag = "  <- noisy? consider enrolling again" if score < 0.5 else ""
        print(f"  sample {i}: {score:.2f}{flag}")
    print(f"\nVoiceprint saved to {paths.voiceprint_path()}")
    return 0


def cmd_run(args) -> int:
    from vozclave import actions, speaker
    from vozclave.engine import Engine, Outcome
    from vozclave.sound import Sound

    config = _load(args)
    verifier = None
    if config.voice.enabled:
        voiceprint = speaker.load_voiceprint(paths.voiceprint_path())
        if voiceprint is None:
            log.error("no voiceprint found: run `vozclave enroll` or set voice.enabled = false")
            return 1
        log.info("loading speaker verification model...")
        embed = speaker.ecapa_embedder(paths.models_dir())
        verifier = speaker.SpeakerVerifier(embed, voiceprint, config.voice.threshold)

    sound = Sound(config.sound.file, config.sound.volume)

    def on_command(command):
        sound.play()
        actions.execute(command)

    matcher, stream = _listen(config)
    engine = Engine(matcher, on_command, verifier, config.cooldown_seconds)
    phrases = ", ".join(f'"{p}"' for c in config.commands for p in c.phrases)
    log.info("listening for: %s", phrases)

    for utt in stream:
        decision = engine.handle(utt)
        score = f" (voice match {decision.score:.2f})" if decision.score is not None else ""
        if decision.outcome is Outcome.EXECUTED:
            log.info('"%s" -> %s%s', utt.text, decision.command.name, score)
        elif decision.outcome is Outcome.WRONG_SPEAKER:
            log.info('"%s" ignored: not your voice%s', utt.text, score)
        elif decision.outcome is Outcome.COOLDOWN:
            log.debug('"%s" ignored: cooldown', utt.text)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vozclave", description="Offline voice commands that only obey your voice."
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("-c", "--config", help="path to the config file")
    parser.add_argument("-v", "--verbose", action="store_true", help="show debug messages")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", help="create a config file from the example")
    p.add_argument("--force", action="store_true", help="overwrite an existing config")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("download-model", help="download the offline speech model")
    p.add_argument("lang", nargs="?", default="es", help="es, en, pt or fr (default: es)")
    p.set_defaults(func=cmd_download_model)

    sub.add_parser("check", help="validate the config and phrases").set_defaults(func=cmd_check)
    sub.add_parser("devices", help="list microphones").set_defaults(func=cmd_devices)

    p = sub.add_parser("enroll", help="record your voice to build your voiceprint")
    p.add_argument("-n", "--samples", type=int, default=8, help="how many samples (default: 8)")
    p.set_defaults(func=cmd_enroll)

    sub.add_parser("run", help="start listening for commands").set_defaults(func=cmd_run)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s  %(message)s",
        datefmt="%H:%M:%S",
    )
    for noisy in ("urllib3", "huggingface_hub", "filelock"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    try:
        return args.func(args)
    except (ConfigError, FileNotFoundError, RuntimeError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
