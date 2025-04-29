KEY_COUNT = 4
HOLD_LENGTH_BEATS = 0 # 0 will produce normal notes
STARTING_LANE = 1
LEFT_TO_RIGHT = True
EQUALISE_SV = True



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
        # if only -f is passed, the arguments should be file paths
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


def is_allowed(file, allowed_files):
    if not (allowed_files == 'all' or isinstance(allowed_files, list)):
        raise TypeError(f'allowed_files expected list, got {type(allowed_files)}')
    if not file.endswith('.osu'):
        logging.debug(f'{file} is not a .osu file')
        return False
    if allowed_files == 'all' or file in allowed_files:
        return True
    return False


def process_diff(filename: str):
    logging.info(f'processing {filename}')
    with open(filename, 'r', encoding='utf-8') as osu_file:
        file_text = osu_file.read()
    
    mode = find_mode(file_text)
    if not mode == 0:
        logging.info('not a standard diff')
        return
    
    file_text = change_hitobject_text(file_text)
    file_text = change_mode(file_text, 3)
    file_text = change_lane_count(file_text, KEY_COUNT)
    file_text = change_diff_name(file_text)
    if EQUALISE_SV:
        file_text = change_slider_multipliers(file_text)
    
    with open(f'{filename[:-4]}[mania].osu', 'w') as mania_file:
        mania_file.write(file_text)


def find_mode(file_text):
    mode = 0
    mode_pattern = re.compile(r'Mode:.*?\n')
    mode_match = mode_pattern.search(file_text)
    if mode_match:
        mode = int(mode_match.group()[5:-1].strip())
    return mode


def change_hitobject_text(file_text):
    hitobjects, (h_text_start, h_text_end) = find_hitobjects(file_text)
    hitobjects = change_hitobjects(file_text, hitobjects)
    hitobject_lines =  [','.join(hitobject) for hitobject in hitobjects]
    hitobject_text = '\n'.join(hitobject_lines)
    file_text = (f"{file_text[:h_text_start]}[HitObjects]\n"
                 f"{hitobject_text}\n"
                 f"\n"
                 f"{file_text[h_text_end:]}")
    return file_text


def find_hitobjects(file_text: str):
    hitobject_pattern = re.compile(r'\[HitObjects\].*?(\[|\Z)', re.DOTALL)
    hitobject_match = hitobject_pattern.search(file_text)
    hitobject_text = hitobject_match.group()[13:-1].strip()
    start, end = hitobject_match.span()
    if hitobject_match.group()[-1] == '[':
        span = (start, end - 1)
    else:
        span = (start, end)
    hitobject_lines = hitobject_text.split('\n')
    hitobjects = [hitobject_line.split(',') for hitobject_line in hitobject_lines]
    return hitobjects, span 


def change_hitobjects(file_text, hitobjects):
    timing_points, _ = find_timing_points(file_text)
    slider_multipliers = [(float(time), -100/float(beat_length))
                          for time, beat_length, _, _, _, _,uninherited, _ in timing_points
                          if not int(uninherited)]
    if not slider_multipliers:
        slider_multipliers = [(0, 1)]
    beat_lengths = [(float(time), float(beat_length))
                    for time, beat_length, _, _, _, _,uninherited, _ in timing_points
                    if int(uninherited)]

    
    base_sv = find_base_sv(file_text)
    for hitobject_index, hitobject in enumerate(hitobjects):
        new_hitobject = change_hitobject(hitobject_index, hitobject, base_sv, slider_multipliers, beat_lengths)
        hitobjects[hitobject_index] = new_hitobject
    return hitobjects


def find_timing_points(file_text: str):
    timing_pattern = re.compile(r'\[TimingPoints\].*?(\[|\Z)', re.DOTALL)
    timing_match = timing_pattern.search(file_text)
    timing_text = timing_match.group()[14:-1].strip()
    start, end = timing_match.span()
    if timing_match.group()[-1] == '[':
        span = (start, end - 1)
    else:
        span = (start, end)
    timing_lines = timing_text.split('\n')
    timing_points = [fill_list(timing_line.split(','), 1, 8) for timing_line in timing_lines]
    return timing_points, span


def fill_list(target, fill_value, max_length):
    return target + [fill_value] * (max_length - len(target))


def find_base_sv(file_text):
    sv_pattern = re.compile(r'SliderMultiplier:.*?\n')
    return float(sv_pattern.search(file_text).group()[17:-1].strip())


def change_hitobject(hitobject_index, hitobject, base_sv, slider_multipliers, beat_lengths):
    HITCIRCLE_BIT = 0
    SLIDER_BIT = 1
    SPINNER_BIT = 3
    MANIA_HOLD_BIT = 7
    MANIA_HOLD_TYPE = str(2**MANIA_HOLD_BIT)
    
    x, y, time, type_ = (int(value) for value in hitobject[:4])
    type_bits = [int(bit) for bit in f'{type_:08b}'[::-1]]
    beat_length = find_timing_value(time, beat_lengths)
    if type_bits[HITCIRCLE_BIT]:
        # hit circle format: x,y,time,type,hitSound,hitSample
        if HOLD_LENGTH_BEATS == 0:
            new_hitobject = hitobject
        else:
            new_hitobject = hitobject[:5] + [str(time + beat_length * HOLD_LENGTH_BEATS)]
            new_hitobject[3] = MANIA_HOLD_TYPE
    elif type_bits[SLIDER_BIT]:
        # slider format: x,y,time,type,hitSound,curveType|curvePoints,slides,length,edgeSounds,edgeSets,hitSample
        slides = int(hitobject[6])
        length = float(hitobject[7])
        slider_velocity = base_sv * find_timing_value(time, slider_multipliers)
        new_hitobject = hitobject[:5] + [str(time + beat_length * slides * length / (100*slider_velocity))]
        new_hitobject[3] = MANIA_HOLD_TYPE
        # doesn't transfer hitsamples from slider
        # (can't be bothered to figure out how the optional parameters work)
    elif type_bits[SPINNER_BIT]:
        # spinner format: x,y,time,type,hitSound,endTime,hitSample
        new_hitobject = hitobject
        new_hitobject[3] = MANIA_HOLD_TYPE
    new_hitobject[0] = str(mania_x_position(hitobject_index))
    # mania hold format: x,y,time,type,hitSound,endTime,hitSample
    return new_hitobject
    

def find_timing_value(target_time, timestamped_values):
    # iterate throgh two copies of timestamped_values, one shifted by 1
    for (_, value), (next_time, _) in zip([(0, 1)] + timestamped_values, timestamped_values + [(-1, 0)]):
        if next_time > target_time:
            return(value)
    return timestamped_values[-1][1]
        

def mania_x_position(hitobject_index):
    PLAYFIELD_WIDTH = 512
    if LEFT_TO_RIGHT:
        lane = (STARTING_LANE - 1 + hitobject_index) % KEY_COUNT
    else:
        lane = (STARTING_LANE - 1 - hitobject_index) % KEY_COUNT
    return ceil(PLAYFIELD_WIDTH * lane/KEY_COUNT)


def change_mode(file_text, mode):
    mode_pattern = re.compile(r'Mode:.*?\n')
    mode_match = mode_pattern.search(file_text)
    if not mode_match:
        general_pattern = re.compile(r'\[General\].*?\n')
        general_match = general_pattern.search(file_text)
        return f'{file_text[:general_match.end()]}Mode: {mode}\n{file_text[general_match.end():]}'
    return f'{file_text[:mode_match.start()]}Mode: {mode}\n{file_text[mode_match.end():]}'


def change_lane_count(file_text, lane_count):
    cs_pattern = re.compile(r'CircleSize:.*?\n')
    cs_match=cs_pattern.search(file_text)
    return f'{file_text[:cs_match.start()]}CircleSize: {lane_count}\n{file_text[cs_match.end():]}'


def change_diff_name(file_text):
    diffname_pattern = re.compile(r'Version:')
    diffname_end = diffname_pattern.search(file_text).end()
    return f'{file_text[:diffname_end]}mania {file_text[diffname_end:]}'


def change_slider_multipliers(file_text):
    DEFAULT_SLIDERMULTIPLIER = '-100'
    timing_points, (t_text_start, t_text_end) = find_timing_points(file_text)
    for timing_point in timing_points:
        uninherited = int(timing_point[6])
        if not uninherited:
            timing_point[1] = DEFAULT_SLIDERMULTIPLIER
    timing_lines = [','.join(timing_point) for timing_point in timing_points]
    timing_text = '\n'.join(timing_lines)
    file_text = (f"{file_text[:t_text_start]}[TimingPoints]\n"
                 f"{timing_text}\n"
                 f"\n"
                 f"{file_text[t_text_end:]}")
    return file_text

    

if __name__ == '__main__':
    main()