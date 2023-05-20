key_count = 4
hold_length_beats = 0 # 0 will produce normal notes
starting_column = 1
left_to_right = True


import logging
import re
import os
import sys
from math import ceil


def main():
    logging.basicConfig(level=logging.INFO)
    logging.debug(f'sys.argv: {sys.argv}')
    converted_anything = False
    if not sys.argv[1:]:
        converted_anything = process_directory('.')
    elif '-d' in sys.argv and '-f' in sys.argv:
        # both flags
        #if -d and -f are passed, the arguments to -f should be filenames
        dir_paths = get_flag_arguments('-d', sys.argv)
        filenames = get_flag_arguments('-f', sys.argv)
        converted_anything = process_directories(dir_paths, filenames)
    elif '-d' in sys.argv:
        # directory flag
        dir_paths = get_flag_arguments('-d', sys.argv)
        converted_anything = process_directories(dir_paths)
    elif '-f' in sys.argv:
        # file flag
        # if only -f is passed, the arguments should be paths to the file, not just filenames.
        file_paths = get_flag_arguments('-f', sys.argv)
        for file_path in file_paths:
            process_diff(file_path)
            converted_anything = True
    else:
        raise ValueError('wrong flag or too many arguments')
    if not converted_anything:
        logging.info('nothing to convert')


def get_flag_arguments(flag, args):
    start = args.index(flag) + 1
    for i, arg in enumerate(args[start:]):
        # find next flag
        if arg[0] == '-':
            stop = start + i
            return args[start:stop]
    return args[start:]
    

def find_timing_value(target_time, timestamped_values):
    for (_, value), (next_time, _) in zip([(0, 1)] + timestamped_values, timestamped_values + [(-1, 0)]):
        if next_time > target_time:
            return(value)
    return timestamped_values[-1][1]


def change_mode_setting(file_text, mode):
    mode_pattern = re.compile(r'Mode:.*?\n')
    mode_match = mode_pattern.search(file_text)
    if not mode_match:
        general_pattern = re.compile(r'\[General\].*?\n')
        general_match = general_pattern.search(file_text)
        return f'{file_text[:general_match.end()]}Mode: {mode}\n{file_text[general_match.end():]}'
    return f'{file_text[:mode_match.start()]}Mode: {mode}\n{file_text[mode_match.end():]}'


def change_column_count(file_text, column_count):
    cs_pattern = re.compile(r'CircleSize:.*?\n')
    cs_match=cs_pattern.search(file_text)
    return f'{file_text[:cs_match.start()]}CircleSize: {column_count}\n{file_text[cs_match.end():]}'


def is_allowed(file, allowed_files):
    if not (allowed_files == 'all' or isinstance(allowed_files, list)):
        raise TypeError(f'allowed_files expected list, got {type(allowed_files)}')
    if not file.endswith('.osu'):
        logging.info('not a .osu file')
        return False
    if allowed_files == 'all' or file in allowed_files:
        return True
    return False


def process_directories(dir_paths, allowed_files='all'):
    converted_anything = False
    for dir_path in dir_paths:
        converted_now = process_directory(dir_path, allowed_files=allowed_files)
        converted_anything = converted_anything or converted_now
    return converted_anything


def process_directory(dir_path, allowed_files='all'):
    converted_anything = False
    walk = list(os.walk(dir_path))
    if not walk:
        raise FileNotFoundError(f'No such file or directory: \'{dir_path}\'')
    for subdir, dirs, files in walk:
        for file in files:
            if is_allowed(file, allowed_files):
                process_diff(os.path.join(subdir, file))
                converted_anything = True
    
    return converted_anything


def process_diff(filename: str):
    logging.info(f'processing {filename}')
    with open(filename) as osu_file:
        file_text = osu_file.read()
    
    mode_pattern = re.compile(r'Mode:.*?\n')
    mode_match = mode_pattern.search(file_text)
    if mode_match:
        mode = int(mode_match.group()[5:-1].strip())
    else:
        mode = 0
    if not mode == 0:
        logging.info('not a standard diff')
        return False
    
    sv_pattern = re.compile(r'SliderMultiplier:.*?\n')
    base_sv = float(sv_pattern.search(file_text).group()[17:-1].strip())
    
    hitobject_pattern = re.compile(r'\[HitObjects\].*?(\[|\Z)', re.DOTALL)
    hitobject_match = hitobject_pattern.search(file_text)
    hitobject_text = hitobject_match.group()[13:-1].strip()
    hitobject_lines = hitobject_text.split('\n')
    
    timing_pattern = re.compile(r'\[TimingPoints\].*?(\[|\Z)', re.DOTALL)
    timing_text = timing_pattern.search(file_text).group()[14:-1].strip()
    timing_lines = timing_text.split('\n')
    timing_points = [timing_line.split(',') + [1]*(8 - len(timing_line.split(','))) for timing_line in timing_lines]
    slider_multipliers = [(float(time), -100/float(beat_length))
                          for time, beat_length, _, _, _, _,uninherited, _ in timing_points
                          if not int(uninherited)]
    if not slider_multipliers:
        slider_multipliers = [(0, 1)]
    beat_lengths = [(float(time), float(beat_length))
                    for time, beat_length, _, _, _, _,uninherited, _ in timing_points
                    if int(uninherited)]
    
    for i, hitobject_line in enumerate(hitobject_lines):
        hitobject = hitobject_line.split(',')
        x, y, time, type_ = (int(value) for value in hitobject[:4])
        type_bits = [int(bit) for bit in f'{type_:08b}'[::-1]]
        beat_length = find_timing_value(time, beat_lengths)
        if type_bits[0]:
            # hit circle: x,y,time,type,hitSound,hitSample
            if hold_length_beats == 0:
                new_hitobject = hitobject
            else:
                new_hitobject = hitobject[:5] + [str(time + beat_length * hold_length_beats)]
                new_hitobject[3] = '128'
        elif type_bits[1]:
            # slider: x,y,time,type,hitSound,curveType|curvePoints,slides,length,edgeSounds,edgeSets,hitSample
            slides = int(hitobject[6])
            length = float(hitobject[7])
            slider_velocity = base_sv * find_timing_value(time, slider_multipliers)
            new_hitobject = hitobject[:5] + [str(time + beat_length * slides * length / (100*slider_velocity))]
            new_hitobject[3] = '128'
            # doesn't transfer hitsamples from slider
            # (can't be bothered to figure out how the optional parameters work)
        elif type_bits[3]:
            # spinner: x,y,time,type,hitSound,endTime,hitSample
            new_hitobject = hitobject
            new_hitobject[3] = '128'
        
        if left_to_right:
            column = (starting_column - 1 + i) % key_count
        else:
            column = (starting_column - 1 - i) % key_count
        new_hitobject[0] = str(ceil(512 * column/key_count))
        hitobject_lines[i] = ','.join(new_hitobject)
        # mania hold: x,y,time,type,hitSound,endTime,hitSample
    
    
    hitobject_text = '\n'.join(hitobject_lines)
    file_text = (f"{file_text[:hitobject_match.start()]}[HitObjects]\n"
                 f"{hitobject_text}\n"
                 f"\n"
                 f"{file_text[hitobject_match.end():]}")
    file_text = change_mode_setting(file_text, 3)
    file_text = change_column_count(file_text, key_count)
    diffname_pattern = re.compile(r'Version:')
    diffname_end = diffname_pattern.search(file_text).end()
    file_text = f'{file_text[:diffname_end]}mania {file_text[diffname_end:]}'
    
    with open(f'{filename[:-4]}[mania].osu', 'w') as mania_file:
        mania_file.write(file_text)
    

if __name__ == '__main__':
    main()