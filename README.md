# Language Redirect generator from Magento

Generate a set of snippets for nginx in order to redirect clients by
different accept-language.

## Install

```sh
pip install --user ./
```

## Usage:

Command line interface syntax:

```sh
language-redirector -d output-directory --language en=english \
  --language it=italian /my/magento-path
```
