"""
Simple module that parses the macOS `pmset -g log` to get usage information to get "screen on" time.

Note that this is an approximation and may change between versions of macOS.
"""


_TARGET_PLATFORM = 'darwin'


def main():
    import sys
    if sys.platform != _TARGET_PLATFORM:
        print(f'Expected macOS (darwin), found {sys.platform}', file=sys.stderr)
        sys.exit(1)
    raise NotImplementedError('Implement me!')


if __name__ == '__main__':
    main()
