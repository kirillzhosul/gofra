"""Apple Linker.

Apple bundles MacOS (Darwin) with `ld` that is `apple-ld`
This linker is only works with Mach-O format object files so it is only suitable for Darwin -> Darwin linkage

It should be selected if you are on MacOS and compiling for Darwin target.
I do not think it can be used outside of that workflow (even something like Linux -> Darwin should not be possible)

According to that cross-compilation for Darwin targets is not possible, and must be done from Darwin (MacOS) host machine
And by that, this linker uses native Darwin (and MacOS, like `xcrun`) possibilities and tools.
"""
