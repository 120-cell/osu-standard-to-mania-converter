# Standard to Mania Converter

A python script that generates osu mania maps from standard maps. The mania maps cycle continuously throught the lanes. Hitcircles can either be turned into normal mania notes or into short holds of a set length.

## Configuration
The first few lines of the script can be changed to configure
- mania key count 
  - default: 4
- length in beats of the holds that hit circles get turned into
  - default: 0 (normal mania notes)
- starting column
  - default: 1
- direction of the column cycle
  - default: left to right

## Running the Script
The script requires only the python standard library (version 3.10 or above).

To run it via the command line use:
```shell
python mania-converter.py
```
By default this will convert all .osu files in the directory of the script. Other files can be specified with additional command line arguments.

`-f` specifies one or more file paths.
```shell
python mania-converter.py -f map1.osu Maps/map2.osu
```

`-d` specifies one or more directories.

The following will convert all .osu files in the `Maps` and `MoreMaps` directories:
```shell
python mania-converter.py -d Maps MoreMaps
```

They can also be used in conjunction, in which case the arguments passed to `-f` should filenames and not full paths.

The following will convert all instances of `map2.osu` and `map3.osu` that appear in `Maps`, `MoreMaps` or their subdirectories:
```shell
python mania-converter.py -d Maps MoreMaps -f map2.osu map3.osu
```













