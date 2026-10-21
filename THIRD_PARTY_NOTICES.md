# License scope and third-party components

The project's Python source, Skill instructions, tests and documentation are licensed under MIT. The MIT grant does not apply to example audio, third-party models, dictionaries, provider voices, or third-party dependencies.

## Recognition model and reference implementation

- [sbintuitions/kana-whisper](https://huggingface.co/sbintuitions/kana-whisper): the model card identifies the model as MIT licensed. Runtime downloads pin revision `88ecb3d79c5846cb4fcf76f4107b84c8fa2acd82`. The weights are **not bundled**. Consult the pinned upstream files and model card for model attribution and conditions.
- [Joyo Kanji Yomi Benchmark](https://github.com/sbintuitions/Joyo-Kanji-Yomi-Benchmark): reference for the Kana Whisper approach. Its MIT notice is reproduced in `licenses/JOYO-MIT.txt`. This project's normalization, review classification and metrics are not Joyo's official scoring implementation.
- [OpenAI Whisper](https://github.com/openai/whisper): upstream architecture/model family used by Kana Whisper. No upstream model weights are bundled here.

## Runtime dependencies

Dependencies are installed separately through Python packaging, not vendored in this repository. Their own licenses continue to apply. In the release verification environment, package metadata identifies SudachiPy and SudachiDict-core as Apache-2.0, PyTorch as BSD-3-Clause, Transformers as Apache-2.0, and SoundFile as BSD-3-Clause. NumPy, SciPy, Accelerate, Hugging Face Hub, Requests, and transitive dependencies retain their respective upstream notices. Dictionary packages may include further notices for their source data; refer to the installed distribution.

## Example audio

Example narration was generated using ElevenLabs on the project operator's paid account, with the voice Jun. It is supplied as demonstration material and is excluded from the source-code MIT license. This repository does not grant rights to voice identity, voice models, trademarks or endorsement. No third-party YouTube audio is bundled.

Provider references: [ElevenLabs Terms](https://elevenlabs.io/terms-of-use), [Voice Library Addendum](https://elevenlabs.io/vla), [API terms](https://elevenlabs.io/elevenapi-terms). Generation provenance is recorded next to the examples. Model weights and voice assets are not included.
