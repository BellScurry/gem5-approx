import os
import random
import re
import argparse
import subprocess
from collections import namedtuple

#  Absolute Path to *THIS* Script
WHERE_AM_I = os.path.dirname(os.path.realpath(__file__)) + '/'

GOLDEN_RUNTIME = {
    'hello':            25129000,               # on HP-Z640
    'stringsearch':     162832000,              # on HP-Z640
    'bitcount':         23239517000,            # on HP-Z640
    'matmul':           102155000,              # on HP-Z640
    'gsm':              15981469000,            # on HP-Z640
    'jpeg':             17629257000,            # on HP-Z640
    'susan':            2355828000,             # on HP-Z640
    'qsort':            17152210500,            # on HP-Z640
    'dijkstra':         27285691000,            # on HP-Z640
    'fft':              28733176000             # on HP-Z640
}

# If no path information in 'local_config.txt',
# assume these paths are available
BENCH_BIN_HOME = WHERE_AM_I + '/tests/test-progs/bin'
BENCH_DATA_HOME = WHERE_AM_I + '/tests/test-progs/data'

# Find path information in 'local_config.txt'
with open(WHERE_AM_I + 'local_config.txt', 'r') as local_config:
    for line in local_config:
        pathdef = line.split(':=')
        lhs = pathdef[0].strip()
        rhs = pathdef[1].strip()
        if lhs == 'BENCH_BIN_HOME':
            BENCH_BIN_HOME = rhs
        if lhs == 'BENCH_DATA_HOME':
            BENCH_DATA_HOME = rhs

BENCH_BINARY = {
    'hello': os.path.abspath(BENCH_BIN_HOME + '/hello_arm'),
    'stringsearch': os.path.abspath(BENCH_BIN_HOME + '/search_small_arm'),
    'bitcount': os.path.abspath(BENCH_BIN_HOME + '/bitcnts_arm'),
    'matmul': os.path.abspath(BENCH_BIN_HOME + '/matmul_arm'),
    'gsm': os.path.abspath(BENCH_BIN_HOME + '/toast_arm'),
    'jpeg': os.path.abspath(BENCH_BIN_HOME + '/cjpeg_arm'),
    'susan': os.path.abspath(BENCH_BIN_HOME + '/susan_arm'),
    'qsort': os.path.abspath(BENCH_BIN_HOME + '/qsort_small_arm'),
    'dijkstra': os.path.abspath(BENCH_BIN_HOME + '/dijkstra_small_arm'),
    'fft': os.path.abspath(BENCH_BIN_HOME + '/fft_arm')
}

BENCH_OPTION = {
    'hello': '',
    'stringsearch': '',
    'bitcount': 75000,
    'matmul': '',
    'gsm': '-fps -c ' + os.path.abspath(BENCH_DATA_HOME + '/small.au'),
    'jpeg': \
        '-dct int -progressive -opt -outfile' \
        ' $BENCH_NAME/$COMP_INFO/result_$IDX ' + \
        os.path.abspath(BENCH_DATA_HOME + '/input_small.ppm'),
    'susan': \
        os.path.abspath(BENCH_DATA_HOME + '/input_small.pgm') + \
        ' $BENCH_NAME/$COMP_INFO/result_$IDX -e',
    'qsort': os.path.abspath(BENCH_DATA_HOME + '/input_small.dat'),
    'dijkstra': os.path.abspath(BENCH_DATA_HOME + '/dijkstra_input.dat'),
    'fft': '4 4096'
}

class ExpManager:
    ##
    #  gem5 commands are like:
    #    <gem5 bin> <gem5 options> <gem5 script> <gem5 script options>
    GEM5_BINARY = os.path.abspath(WHERE_AM_I + '/build/ARM/gem5.opt')
    GEM5_SCRIPT = os.path.abspath(WHERE_AM_I + '/configs/example/se.py')

    # gem5 MinorCPU bits
    BIT_LENGTH = {
        'f1ToF2': 512,       # 64 Byte = 512 bit
        'f2ToD': 64,
        # 1 Byte = 8 bit, sizeof(RegIndex) = 2
        # MAX(n(src reg)) = 34, MAX(n(dest reg)) = 8
        # numInsts = 2
        'dToE': 8 * 2 * (34+8) * 2,
        'eToF1': 32,
        'f2ToF1': 32
    }

    # Summary of single fault-injection experiment result
    SINGLE_FI_RESULT = namedtuple('SingleFIResult', \
                                  'failure failure_reason runtime_percent')

    @staticmethod
    def run_golden(bench_name, flag):
        # Directory name
        outdir = bench_name + '/golden/'

        # File names
        stdout_file = 'simout_golden'
        stderr_file = 'simerr_golden'
        stats_file = 'stats_golden.txt'
        output_file = 'result_golden'
        debug_file = 'debug_golden.txt'

        # gem5 options
        gem5_redirection = '-re'
        gem5_outdir = '--outdir=' + outdir
        gem5_stdout_file = '--stdout-file=' + stdout_file
        gem5_stderr_file = '--stderr-file=' + stderr_file
        gem5_stats_file = '--stats-file=' + stats_file
        gem5_debug_file = '--debug-file=debug_golden.txt'

        # Process given debug flags
        gem5_debug_flags = ''
        if flag and len(flag) > 0:
            gem5_debug_flags = '--debug-flags=' + ','.join(flag)

        # Combine gem5 options into one string
        gem5_option = ' '.join([gem5_redirection, \
                                gem5_outdir, \
                                gem5_stdout_file, \
                                gem5_stderr_file, \
                                gem5_stats_file, \
                                gem5_debug_file, \
                                gem5_debug_flags])

        # gem5 script options
        gem5script_env = '--cpu-type=MinorCPU --caches -n 1'
        gem5script_bench_binary = '-c ' + BENCH_BINARY[bench_name]
        gem5script_bench_option = BENCH_OPTION[bench_name]
        if gem5script_bench_option:
            gem5script_bench_option = '-o ' + '\"' + \
                str(gem5script_bench_option) + '\"'
            gem5script_bench_option = gem5script_bench_option.\
                replace('$BENCH_NAME', bench_name)
            gem5script_bench_option = gem5script_bench_option.\
                replace('$IDX', 'golden')
            gem5script_bench_option = gem5script_bench_option.\
                replace('$COMP_INFO', 'golden')

        # Output file option needs directory name in which it is located
        gem5script_output = '--output=' + outdir + output_file

        # Combile gem5 script options into one string
        gem5script_option = ' '.join([gem5script_env, \
                                      gem5script_bench_binary, \
                                      gem5script_bench_option, \
                                      gem5script_output])

        # Generate whole gem5 command
        gem5_command = ' '.join([ExpManager.GEM5_BINARY, \
                                 gem5_option, \
                                 ExpManager.GEM5_SCRIPT, \
                                 gem5script_option])

        # Run simulation
        subprocess.call(gem5_command, shell=True)

    @staticmethod
    def inject_single(inj_time, inj_bit, inj_comp1, inj_comp2, \
                      idx=0, bench_name='stringsearch', \
                      flag=['FI'], remove_result_file=True):
        ##
        #  Assume only one fault is injected in each experiment
        #

        # Component Info
        comp_info = '_'.join([inj_comp1, inj_comp2])

        # Directory name
        outdir = bench_name + '/' + comp_info + '/'

        # File names
        stdout_file = 'simout_' + str(idx)
        stderr_file = 'simerr_' + str(idx)
        stats_file = 'stats_' + str(idx) + '.txt'
        output_file = 'result_' + str(idx).zfill(6)
        debug_file = 'debug_' + str(idx) + '.txt'

        # gem5 options
        gem5_redirection = '-re'
        gem5_outdir = '--outdir=' + outdir
        gem5_stdout_file = '--stdout-file=' + stdout_file
        gem5_stderr_file = '--stderr-file=' + stderr_file
        gem5_stats_file = '--stats-file=' + stats_file
        gem5_debug_file = '--debug-file=' + debug_file

        # Process given debug flags
        gem5_debug_flags = ''
        if flag and len(flag) > 0:
            gem5_debug_flags = '--debug-flags=' + ','.join(flag)

        # Combine gem5 options into one string
        gem5_option = ' '.join([gem5_redirection, \
                                gem5_outdir, \
                                gem5_stdout_file, \
                                gem5_stderr_file, \
                                gem5_stats_file, \
                                gem5_debug_file, \
                                gem5_debug_flags])

        # gem5 script options
        gem5script_env = '--cpu-type=MinorCPU --caches -n 1'
        gem5script_bench_binary = '-c ' + BENCH_BINARY[bench_name]
        gem5script_bench_option = BENCH_OPTION[bench_name]
        if gem5script_bench_option:
            gem5script_bench_option = '-o ' + '\"' + \
                str(gem5script_bench_option) + '\"'
            gem5script_bench_option = gem5script_bench_option.\
                replace('$BENCH_NAME', bench_name)
            gem5script_bench_option = gem5script_bench_option.\
                replace('$IDX', str(idx).zfill(6))
            gem5script_bench_option = gem5script_bench_option.\
                replace('$COMP_INFO', comp_info)

        # Output file option needs directory name in which it is located
        gem5script_output = '--output=' + outdir + output_file

        # Fault injection info
        runtime_limit = 2 * int(GOLDEN_RUNTIME[bench_name])
        gem5script_injectTime = '--injectTime=' + str(inj_time)
        gem5script_injectLoc = '--injectLoc=' + str(inj_bit)
        gem5script_injectArch = '--injectArch=' + inj_comp1
        gem5script_injectComp = '--injectComp=' + inj_comp2
        gem5script_runtime_limit = ' '.join(['-m', str(runtime_limit)])


        # Combine gem5 sciprt options into one string
        gem5script_option = ' '.join([gem5script_env, \
                                      gem5script_bench_binary, \
                                      gem5script_bench_option, \
                                      gem5script_output, \
                                      gem5script_injectTime, \
                                      gem5script_injectLoc, \
                                      gem5script_injectArch, \
                                      gem5script_injectComp, \
                                      gem5script_runtime_limit])

        # Generate whole gem5 command
        gem5_command = ' '.join([ExpManager.GEM5_BINARY, \
                                 gem5_option, \
                                 ExpManager.GEM5_SCRIPT, \
                                 gem5script_option])

        # Run simulation
        subprocess.call(gem5_command, shell=True)

        # Summarize experiment info, then remove result file to save storage
        this_failure = 'NF'
        this_failure_reason = ''
        this_runtime_percent = str(0)

        ## (1) Check if it is 'System Halt'
        ##     Note that every time stats file will be made,
        ##     although its contents can be empty
        stats_file_location = os.path.abspath(WHERE_AM_I + \
                                              outdir + stats_file)
        if (not os.path.isfile(stats_file_location)) or \
                os.path.getsize(stats_file_location) == 0:
            this_failure = 'F'
            this_failure_reason = 'SYSHALT'
            this_runtime_percent = 'failure'
        else:
            ## (2) Check if it is 'Timing Failure'
            runtime = 0
            with open(stats_file_location, 'r') as stats_file_stream:
                for line in stats_file_stream:
                    if "sim_ticks" in line:
                        runtime = int(re.findall('\d+', line)[0])
                        # Fault injection runtime
                        # compared to golden runtime (%)
                        this_runtime_percent = \
                            str(round(100 * float(runtime) \
                                      / float(GOLDEN_RUNTIME[bench_name]), \
                                      2)) + '%'
                        break

            ### It is 'Timing Failure' if its runtime is over the limit
            if runtime >= int(runtime_limit):
                this_failure = 'F'
                this_failure_reason = 'TIME-FAILURE'
                this_runtime_percent = '>200%'

            ## (3) Check if it is 'SDC' (Silent Data Corruption)
            output_file_location = os.path.abspath(WHERE_AM_I + \
                                                   outdir + \
                                                   output_file)
            if (this_failure == 'F') and \
                os.path.isfile(output_file_location):
                golden_output_file_location = \
                    os.path.abspath(WHERE_AM_I + \
                                    '/golden' + \
                                    '/golden_output_' + bench_name)
                ### Compare benchmark output file with golden output file
                if subprocess.call(' '.join(['diff', \
                                             '-s', \
                                             output_file_location, \
                                             golden_output_file_location, \
                                             '>/dev/null', '| echo $?']), \
                                   shell=True) != '0':
                    this_failure = 'F'
                    this_failure_reason = 'SDC'
                ### Remove benchmark file
                if remove_result_file:
                    subprocess.call('rm ' + output_file_location, shell=True)

        # Return a named tuple, which summarizes a single experiment result
        return ExpManager.\
            SINGLE_FI_RESULT(failure=this_failure, \
                             failure_reason=this_failure_reason, \
                             runtime_percent=this_runtime_percent)

    @staticmethod
    def inject_random(inj_comp1, inj_comp2, \
                      start_idx=1, end_idx=1000, \
                      bench_name='stringsearch', flag=['FI']):
        runtime = GOLDEN_RUNTIME[bench_name]

        #  Digest - All stat & log files are too large to store
        subprocess.call('mkdir ' + bench_name, shell=True)
        comp_info = '_'.join([inj_comp1, inj_comp2])
        exp_info = '_'.join([bench_name, \
                             comp_info, \
                             str(start_idx), \
                             str(end_idx)])
        digest = open(bench_name + '/' + 'digest_' + exp_info + '.txt', 'w')

        #  Write headline of digest
        digest.write('\t'.join(['exp#', 'time', 'bit', \
                                'F/NF', 'comp2', 'inst', \
                                'runtime', 'benchmark', 'change/etc']) + '\n')
        digest.write('-' * 80 + '\n')

        #  Iterating several experiments
        for idx in range(int(start_idx), int(end_idx)+1):
            #  Pick random numbers
            rand_time = str(random.randrange(1, GOLDEN_RUNTIME[bench_name]))
            rand_bit = str(random.\
                           randrange(0, ExpManager.BIT_LENGTH[inj_comp2]))

            #  Do single experiment
            single_exp_result = \
                ExpManager.inject_single(rand_time, \
                                         rand_bit, \
                                         inj_comp1, \
                                         inj_comp2, \
                                         idx, \
                                         bench_name, flag)

            # <index> <inj time> <inj loc>
            para1 = '\t'.join([str(idx), rand_time, rand_bit])

            ##
            #  Read debug file
            #
            change_by_flip = ''
            target_mnemonic = ''
            bubble = False
            outdir = bench_name + '/' + comp_info
            with open(outdir + '/' + 'debug_' + str(idx) + '.txt', 'r') \
                as debug_read:
                for line in debug_read:
                    if '->' in line:
                        change_by_flip = ':'.join(line.split(':')[2:]).strip()
                    if '* inst:' in line:
                        change_by_flip = line.split('* inst:')[1].strip()
                    if 'BUBBLE' in line:
                        change_by_flip = \
                            'BUBBLE' + line.split('BUBBLE')[1].strip()
                        bubble = True
                    if 'FAULT' in line:
                        change_by_flip = 'FAULT'
                        bubble = True
                    if 'Flip inst' in line:
                        """
                        [$->F] Example
83207000: global:      * Flip inst:
0xe50b64a4   str   r6, [fp, #-1188] -> 0xe10b64a4   tst   fp, r4, LSR #9
                        """
                        """
                        [F->D] Example
76628500: global:      * Flip inst:
0xe3530c0a   cmps   r3, #2560 -> 0xe3730c0a   cmns   r3, #2560
                        """
                        target_mnemonic = line.split(':')[3].split()[1]
                    if 'target op' in line:
                        """
                        [D->E] Example
151534500: global:      * target op: ARM uop  ldr   r4, [fp, #-1116]
                        """
                        target_mnemonic = line.split(':')[3].split()[2]

                        """
                        [E->$] Example
43809000: global:      * Flip target address: 0x1da88 -> 0x1da98
                        """


            # <F/NF>
            # <comp2>
            # <inst (=target mnemonic)>
            # <runtime>
            # <bench name>
            # <change/etc>
            if (not bubble) and single_exp_result.failure:
                isFailure = 'F'
            else:
                isFailure = 'NF'
            para2 = '\t'.join([isFailure, \
                               inj_comp2, \
                               target_mnemonic, \
                               single_exp_result.runtime_percent, \
                               bench_name, \
                               change_by_flip])

            # Write one line to digest file
            digest.write('\t'.join([para1, para2]).strip() + '\n')

        digest.close()


if __name__ == '__main__':
    # Argument Format
    parser = argparse.ArgumentParser()
    parser.add_argument('bench_name', \
                        metavar='<bench name>', help='Benchmark\'s name')
    parser.add_argument('-g', '--golden', \
                        action='store_true', \
                        help='No fault injection to get golden output')
    parser.add_argument('--sim', \
                        action='store', \
                        nargs=1, help='Simulation Binary')
    parser.add_argument('-i', '--index', \
                        action='store', nargs=2, help='Experiment Number')
    parser.add_argument('-f', '--flag', \
                        action='store', \
                        nargs='*', help='All gem5 debug flags')
    parser.add_argument('--inject', \
                        action='store', \
                        nargs=2, help='Injection <time> <location>')
    parser.add_argument('--comp2', \
                        action='store', \
                        help='Injection to: ' \
                        'f1ToF2 | f2ToD | dToE | f2ToF1 | eToF1')

    ##
    #  End parsing & Run gem5
    args = parser.parse_args()

    if args.sim:
        ExpManager.GEM5_BINARY = \
            os.path.abspath(WHERE_AM_I + '/build/ARM/' + str(args.sim[0]))

    if args.golden:
        # Golden Run
        ExpManager.run_golden(args.bench_name, args.flag)
    elif args.inject:
        # Non-random Fault Injection
        ExpManager.inject_single(args.inject[0], \
                                 args.inject[1], \
                                 'PipeReg', \
                                 args.comp2, \
                                 'inject', \
                                 args.bench_name, \
                                 args.flag)
    else:
        ExpManager.inject_random('PipeReg', \
                                 args.comp2, \
                                 args.index[0], \
                                 args.index[1], \
                                 args.bench_name, \
                                 args.flag)
