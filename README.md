# stack-sparrow
A Code LLM - based on GPT-4-Turbo and Assistant API

[![PyPI - Version](https://img.shields.io/pypi/v/stack-sparrow)](https://pypi.org/project/stack-sparrow/)
[![Discord](https://img.shields.io/badge/Discord-%235865F2.svg?style=flat&logo=discord&logoColor=white)](https://discord.gg/ZNvjdwrg)

## Installation
```bash
pip install -U stack-sparrow
```

# Examples

- [Review #1](https://mod0.ai/stack-sparrow/review-semantics): Flag semantics issue
- [Review #2](https://mod0.ai/stack-sparrow/review-basic-issues): Flag broken code
- [Review #3](https://mod0.ai/stack-sparrow/review-basic-issues): Successful Review

# Demo



https://github.com/akhilravidas/stack-sparrow/assets/104069/1259364c-9d04-497b-a81b-c78decb711cf




## Usage

`sparrow` will create an OpenAI assistant on your account on the first run. You can view this assistant and tweak its base instructions at: https://platform.openai.com/assistants

Review a file

```
sparrow review path/to/file
```

Review your current commit

```
sparrow review HEAD
```

Review a range of commits

```
sparrow review HEAD HEAD~5
```

Review a different repository

```
sparrow review HEAD --repo_path path/to/repo
```

## Contributing

Please feel free to open issues, submit pull requests or hang out with me and other interested folks on [Discord](https://discord.gg/ZNvjdwrg).

## License

This project is licensed under the terms of the MIT License.
