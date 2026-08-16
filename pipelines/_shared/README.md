# Shared pipeline contracts

Files in this directory contain orchestration that is genuinely shared by multiple pipelines.

They are not public actions and must never be loaded globally. An owning pipeline must opt in explicitly from its `READ` section.

Keep academic purpose, scope rules, artifact-specific commands and exceptions in the owning pipeline. Move logic here only when behavior is identical across every consumer.
