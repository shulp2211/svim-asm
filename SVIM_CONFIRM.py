from __future__ import print_function

__version__ = '0.2'
__author__ = 'David Heller'

import sys
import argparse
import os
import pickle
import gzip
import logging
import configparser
import itertools

from subprocess import Popen, PIPE, call
from collections import defaultdict
from time import strftime, localtime
from math import pow, sqrt
from multiprocessing import Pool

import pysam
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from Bio import SeqIO
from matplotlib.backends.backend_pdf import PdfPages

from SVIM_readtails import confirm_del, confirm_ins, confirm_inv, confirm_del2, confirm_ins2, confirm_inv2
from SVIM_COLLECT import read_parameters


def parse_arguments():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                     description="""SVIM (pronounced SWIM) is a structural variant caller for long reads. 
It combines full alignment analysis, split-read mapping, and read-tail mapping to 
distinguish five classes of structural variants. SVIM discriminates between similar 
SV classes such as interspersed duplications and cut&paste insertions and is unique 
in its capability of extracting both the genomic origin and destination of insertions 
and duplications.

SVIM consists of three programs SVIM-COLLECT, SVIM-CONFIRM, and SVIM-COMBINE. You are running SVIM-CONFIRM 
which confirms SV evidences using read-tail mapping.""")
    parser.add_argument('--version', '-v', action='version', version='%(prog)s {version}'.format(version=__version__))
    parser.add_argument('working_dir', type=str, help='working directory')
    parser.add_argument('reads', type=str, help='Read file (FASTA, FASTQ, gzipped FASTA and FASTQ)')
    parser.add_argument('genome', type=str, help='Reference genome file (FASTA)')
    parser.add_argument('--config', type=str, default="{0}/default_config.cfg".format(os.path.dirname(os.path.realpath(__file__))), help='configuration file, default: {0}/default_config.cfg'.format(os.path.dirname(os.path.realpath(__file__))))
    parser.add_argument('--obj_file', '-i', type=argparse.FileType('rb'), help='Path of .obj file to load (default: working_dir/sv_evidences.obj')
    parser.add_argument('--confirm_del_min', type=int, default=0, help='Confirm deletion evidence clusters with this score or larger.')
    parser.add_argument('--confirm_ins_min', type=int, default=0, help='Confirm insertion evidence clusters with this score or larger')
    parser.add_argument('--confirm_inv_min', type=int, default=0, help='Confirm inversion evidence clusters with this score or larger')
    parser.add_argument('--cores', type=int, default=1, help='CPU cores to use for alignment and confirmation')
    parser.add_argument('--debug_confirm', action='store_true', help='print dot plots when confirming SV evidence clusters')
    return parser.parse_args()


def guess_file_type(reads_path):
    if reads_path.endswith(".fa") or reads_path.endswith(".fasta") or reads_path.endswith(".FA"):
        logging.info("Recognized reads file as FASTA format.")
        return "fasta"
    elif reads_path.endswith(".fq") or reads_path.endswith(".fastq") or reads_path.endswith(".FQ"):
        logging.info("Recognized reads file as FASTQ format.")
        return "fastq"
    elif reads_path.endswith(".fa.gz") or reads_path.endswith(".fasta.gz") or reads_path.endswith(".fa.gzip") or reads_path.endswith(".fasta.gzip"):
        logging.info("Recognized reads file as gzipped FASTA format.")
        return "fasta_gzip"
    elif reads_path.endswith(".fq.gz") or reads_path.endswith(".fastq.gz") or reads_path.endswith(".fq.gzip") or reads_path.endswith(".fastq.gzip"):
        logging.info("Recognized reads file as gzipped FASTQ format.")
        return "fastq_gzip"
    elif reads_path.endswith(".fa.fn"):
        logging.info("Recognized reads file as FASTA file list format.")
        return "list" 
    else:
        logging.error("Unknown file ending of file {0}. Exiting.".format(reads_path))
        return "unknown"


def create_tail_files(working_dir, reads_path, reads_type, span):
    """Create FASTA files with read tails and full reads if they do not exist."""
    if not os.path.exists(working_dir):
        logging.error("Given working directory does not exist")
        sys.exit()

    reads_file_prefix = os.path.splitext(os.path.basename(reads_path))[0]

    if not os.path.exists("{0}/{1}_left.fa".format(working_dir, reads_file_prefix)):
        left_file = open("{0}/{1}_left.fa".format(working_dir, reads_file_prefix), 'w')
        write_left = True
    else:
        write_left = False
        logging.warning("FASTA file for left tails exists. Skip")

    if not os.path.exists("{0}/{1}_right.fa".format(working_dir, reads_file_prefix)):
        right_file = open("{0}/{1}_right.fa".format(working_dir, reads_file_prefix), 'w')
        write_right = True
    else:
        write_right = False
        logging.warning("FASTA file for right tails exists. Skip")

    if reads_type == "fasta_gzip" or reads_type == "fastq_gzip":
        full_reads_path = "{0}/{1}.fa".format(working_dir, reads_file_prefix)
        if not os.path.exists(full_reads_path):
            full_file = open(full_reads_path, 'w')
            write_full = True
        else:
            write_full = False
            logging.warning("FASTA file for full reads exists. Skip")
    else:
        full_reads_path = reads_path
        write_full = False

    if write_left or write_right or write_full:
        if reads_type == "fasta" or reads_type == "fastq":
            reads_file = open(reads_path, "r")
        elif reads_type == "fasta_gzip" or reads_type == "fastq_gzip":
            reads_file = gzip.open(reads_path, "rb")
        
        if reads_type == "fasta" or reads_type == "fasta_gzip":
            sequence = ""
            for line in reads_file:
                if line.startswith('>'):
                    if sequence != "":
                        if len(sequence) > 2000:
                            if write_left:
                                prefix = sequence[:span]
                                print(">" + read_name, file=left_file)
                                print(prefix, file=left_file)
                            if write_right:
                                suffix = sequence[-span:]
                                print(">" + read_name, file=right_file)
                                print(suffix, file=right_file)
                        if write_full:
                            print(">" + read_name, file=full_file)
                            print(sequence, file=full_file)
                    read_name = line.strip()[1:]
                    sequence = ""
                else:
                    sequence += line.strip()
            if sequence != "":
                if len(sequence) > 2000:
                    if write_left:
                        prefix = sequence[:span]
                        print(">" + read_name, file=left_file)
                        print(prefix, file=left_file)
                    if write_right:
                        suffix = sequence[-span:]
                        print(">" + read_name, file=right_file)
                        print(suffix, file=right_file)
                if write_full:
                    print(">" + read_name, file=full_file)
                    print(sequence, file=full_file)
            reads_file.close()
        elif reads_type == "fastq" or reads_type == "fastq_gzip": 
            sequence_line_is_next = False
            for line in reads_file:
                if line.startswith('@'):
                    read_name = line.strip()[1:]
                    sequence_line_is_next = True
                elif sequence_line_is_next:
                    sequence_line_is_next = False
                    sequence = line.strip()
                    if len(sequence) > 2000:
                        if write_left:
                            prefix = sequence[:span]
                            print(">" + read_name, file=left_file)
                            print(prefix, file=left_file)
                        if write_right:
                            suffix = sequence[-span:]
                            print(">" + read_name, file=right_file)
                            print(suffix, file=right_file)
                    if write_full:
                        print(">" + read_name, file=full_file)
                        print(sequence, file=full_file)
            reads_file.close()
    
    if write_left:
        left_file.close()
    if write_right:
        right_file.close()
    if write_full:
        full_file.close()

    logging.info("Read tail and full read files written")
    return full_reads_path


def run_tail_alignments(working_dir, genome, reads_path, cores):
    """Align read tails with NGM-LR."""
    reads_file_prefix = os.path.splitext(os.path.basename(reads_path))[0]
    left_fa = "{0}/{1}_left.fa".format(working_dir, reads_file_prefix)
    left_aln = "{0}/{1}_left_aln.coordsorted.bam".format(working_dir, reads_file_prefix)
    left_aln_index = "{0}/{1}_left_aln.coordsorted.bam.bai".format(working_dir, reads_file_prefix)
    right_fa = "{0}/{1}_right.fa".format(working_dir, reads_file_prefix)
    right_aln = "{0}/{1}_right_aln.coordsorted.bam".format(working_dir, reads_file_prefix)
    right_aln_index = "{0}/{1}_right_aln.coordsorted.bam.bai".format(working_dir, reads_file_prefix)
    full_fa = "{0}/{1}.fa".format(working_dir, reads_file_prefix)
    full_aln = "{0}/{1}_aln.coordsorted.bam".format(working_dir, reads_file_prefix)
    full_aln_index = "{0}/{1}_aln.coordsorted.bam.bai".format(working_dir, reads_file_prefix)

    if not os.path.exists(left_aln):
        bwa = Popen(['ngmlr',
                     '-t', str(cores), '-r', genome, '-q', left_fa], stdout=PIPE)
        view = Popen(['samtools',
                      'view', '-b', '-@', str(cores)], stdin=bwa.stdout, stdout=PIPE)
        sort = Popen(['samtools',
                      'sort', '-@', str(cores), '-o', left_aln], stdin=view.stdout)
        sort.wait()
    else:
        logging.warning("Alignment for left sequences exists. Skip")

    if not os.path.exists(left_aln_index):
        call(['samtools',
                      'index', left_aln])
    else:
        logging.warning("Alignment index for left sequences exists. Skip")

    if not os.path.exists(right_aln):
        bwa = Popen(['ngmlr',
                     '-t', str(cores), '-r', genome, '-q', right_fa], stdout=PIPE)
        view = Popen(['samtools',
                      'view', '-b', '-@', str(cores)], stdin=bwa.stdout, stdout=PIPE)
        sort = Popen(['samtools',
                      'sort', '-@', str(cores), '-o', right_aln], stdin=view.stdout)
        sort.wait()
    else:
        logging.warning("Alignment for right sequences exists. Skip")

    if not os.path.exists(right_aln_index):
        call(['samtools',
                      'index', right_aln])
    else:
        logging.warning("Alignment index for right sequences exists. Skip")

    logging.info("Tail alignments finished")

    if not os.path.exists(full_aln):
        ngmlr = Popen(['ngmlr',
                    '-t', str(cores), '-r', genome, '-q', os.path.realpath(reads_path)], stdout=PIPE)
        view = Popen(['samtools',
                    'view', '-b', '-@', str(cores)], stdin=ngmlr.stdout, stdout=PIPE)
        sort = Popen(['samtools',
                    'sort', '-@', str(cores), '-o', full_aln],
                    stdin=view.stdout)
        sort.wait()
        logging.info("Alignment finished")
    else:
        logging.warning("Alignment for full sequences exists. Skip")

    if not os.path.exists(full_aln_index):
        call(['samtools',
                    'index', full_aln])
    else:
        logging.warning("Alignment index for full sequences exists. Skip")
    
    logging.info("Full alignment finished")


def confirm_clusters_in_contig(evidence_clusters, type, left_aln, right_aln, full_aln, full_reads_path, genome_path, parameters):
    reads = SeqIO.index_db(full_reads_path + ".idx", full_reads_path, "fasta")
    reference =SeqIO.index_db(genome_path + ".idx", genome_path, "fasta")

    left_bam = pysam.AlignmentFile(left_aln)
    right_bam = pysam.AlignmentFile(right_aln)
    full_bam = pysam.AlignmentFile(full_aln)

    current_contig = evidence_clusters[0].get_source()[0]
    contig_record = reference[current_contig]
    logging.info("Confirm {0} evidence clusters in contig {1}..".format(type, current_contig))

    for cluster in evidence_clusters:
        if type == "deletion":
            successful_kmer_confirmations, total_kmer_confirmations = confirm_del(left_bam, right_bam, cluster, reads, contig_record, parameters)
            read_evidences, read_contradictions = confirm_del2(full_bam, cluster, parameters)
        if type == "insertion":
            successful_kmer_confirmations, total_kmer_confirmations = confirm_ins(left_bam, right_bam, cluster, reads, contig_record, parameters)
            read_evidences, read_contradictions = confirm_ins2(full_bam, cluster, parameters)
        if type == "inversion":
            successful_kmer_confirmations, total_kmer_confirmations = confirm_inv(left_bam, right_bam, cluster, reads, contig_record, parameters)
            read_evidences, read_contradictions = confirm_inv2(full_bam, cluster, parameters)

        if total_kmer_confirmations + read_evidences + read_contradictions == 0:
            score = -1
        elif type == "inversion":
            if cluster.score == 0:
                score = 0
            else:
                #Number of confirmed (maximally 100)
                num_confirmed =  min(100, successful_kmer_confirmations + cluster.score)
                #Rate of confirmed in percent
                rate_confirmed =  (cluster.score + successful_kmer_confirmations) * 100 / (total_kmer_confirmations + cluster.score + read_contradictions)
                #compute score as the sum of square roots, scale to a range between 0 and 100
                score = 5 * (sqrt(num_confirmed) + sqrt(rate_confirmed))
        else:
            #Number of confirmed (maximally 100)
            num_confirmed =  min(100, successful_kmer_confirmations + read_evidences)
            #Rate of confirmed in percent
            rate_confirmed =  (read_evidences + successful_kmer_confirmations) * 100 / (total_kmer_confirmations + read_evidences + read_contradictions)
            #compute score as the sum of square roots, scale to a range between 0 and 100
            score = 5 * (sqrt(num_confirmed) + sqrt(rate_confirmed))

        cluster.score = score

    return evidence_clusters

def main():
    # Fetch command-line options and configuration file values and set parameters accordingly
    options = parse_arguments()
    parameters = read_parameters(options)

    # Set up logging
    logFormatter = logging.Formatter("%(asctime)s [%(levelname)-7.7s]  %(message)s")
    rootLogger = logging.getLogger()
    rootLogger.setLevel(logging.INFO)

    fileHandler = logging.FileHandler("{0}/SVIM-CONFIRM_{1}.log".format(options.working_dir, strftime("%y%m%d_%H%M%S", localtime())), mode="w")
    fileHandler.setFormatter(logFormatter)
    rootLogger.addHandler(fileHandler)

    consoleHandler = logging.StreamHandler()
    consoleHandler.setFormatter(logFormatter)
    rootLogger.addHandler(consoleHandler)

    logging.info("****************** Start SVIM-CONFIRM, version {0} ******************".format(__version__))
    logging.info("CMD: python {0}".format(" ".join(sys.argv)))
    logging.info("WORKING DIR: {0}".format(os.path.abspath(options.working_dir)))

    if options.obj_file:
        logging.info("INPUT: {0}".format(os.path.abspath(options.obj_file.name)))
        evidences_file = options.obj_file
    else:
        logging.info("INPUT: {0}".format(os.path.abspath(options.working_dir + '/sv_evidences.obj')))
        evidences_file = open(options.working_dir + '/sv_evidences.obj', 'rb')

    logging.info("Loading object file created by SVIM-COLLECT.")
    evidence_clusters = pickle.load(evidences_file)
    deletion_evidence_clusters, insertion_evidence_clusters, inversion_evidence_clusters, tandem_duplication_evidence_clusters, insertion_from_evidence_clusters, completed_translocations = evidence_clusters
    evidences_file.close()

    reads_type = guess_file_type(options.reads)
    full_reads_path = create_tail_files(options.working_dir, options.reads, reads_type, parameters["tail_span"])
    run_tail_alignments(options.working_dir, options.genome, full_reads_path, options.cores)

    ####################
    # Confirm clusters #
    ####################
    reads_file_prefix = os.path.splitext(os.path.basename(full_reads_path))[0]
    left_aln = "{0}/{1}_left_aln.coordsorted.bam".format(options.working_dir, reads_file_prefix)
    right_aln = "{0}/{1}_right_aln.coordsorted.bam".format(options.working_dir, reads_file_prefix)
    full_aln = "{0}/{1}_aln.coordsorted.bam".format(options.working_dir, reads_file_prefix)
    left_bam = pysam.AlignmentFile(left_aln)
    right_bam = pysam.AlignmentFile(right_aln)
    full_bam = pysam.AlignmentFile(full_aln)

    reads = SeqIO.index_db(full_reads_path + ".idx", full_reads_path, "fasta")
    reference =SeqIO.index_db(options.genome + ".idx", options.genome, "fasta")
    pool = Pool(processes=options.cores)
    logging.info("Indexing reads and reference finished")

    #DELETIONS
    num_confirming_del = sum(1 for del_cluster in deletion_evidence_clusters if del_cluster.score >= options.confirm_del_min)
    logging.info("Confirming {0} deletion evidence clusters with scores above {1}".format(num_confirming_del, options.confirm_del_min))

    dels_to_confirm_dict = defaultdict(list)
    dels_not_to_confirm = list()
    for del_cluster in deletion_evidence_clusters:
        if del_cluster.score >= options.confirm_del_min:
            current_contig = del_cluster.get_source()[0]
            dels_to_confirm_dict[current_contig].append(del_cluster)
        else:
            del_cluster.score = 0
            dels_not_to_confirm.append(del_cluster)

    inputs = []
    for contig in sorted(dels_to_confirm_dict.keys()):
        inputs.append((dels_to_confirm_dict[contig], "deletion", left_aln, right_aln, full_aln, full_reads_path, options.genome, parameters))
    results = pool.starmap(confirm_clusters_in_contig, inputs)
    deletion_evidence_clusters = list(itertools.chain.from_iterable(results)) + dels_not_to_confirm

    #INSERTIONS
    num_confirming_ins = sum(1 for ins_cluster in insertion_evidence_clusters if ins_cluster.score >= options.confirm_ins_min)
    logging.info("Confirming {0} insertion evidence clusters with scores above {1}".format(num_confirming_ins, options.confirm_ins_min))

    ins_to_confirm_dict = defaultdict(list)
    ins_not_to_confirm = list()
    for ins_cluster in insertion_evidence_clusters:
        if ins_cluster.score >= options.confirm_ins_min:
            current_contig = ins_cluster.get_source()[0]
            ins_to_confirm_dict[current_contig].append(ins_cluster)
        else:
            ins_cluster.score = 0
            ins_not_to_confirm.append(ins_cluster)

    inputs = []
    for contig in sorted(ins_to_confirm_dict.keys()):
        inputs.append((ins_to_confirm_dict[contig], "insertion", left_aln, right_aln, full_aln, full_reads_path, options.genome, parameters))
    results = pool.starmap(confirm_clusters_in_contig, inputs)
    insertion_evidence_clusters = list(itertools.chain.from_iterable(results)) + ins_not_to_confirm

    #INVERSIONS
    num_confirming_inv = sum(1 for inv_cluster in inversion_evidence_clusters if inv_cluster.score >= options.confirm_inv_min)
    logging.info("Confirming {0} inversion evidence clusters with scores above {1}".format(num_confirming_inv, options.confirm_inv_min))

    inv_to_confirm_dict = defaultdict(list)
    inv_not_to_confirm = list()
    for inv_cluster in inversion_evidence_clusters:
        contig, start, end = inv_cluster.get_source()
        if inv_cluster.score >= options.confirm_inv_min and end - start <= parameters["max_sv_size"]:
            current_contig = contig
            inv_to_confirm_dict[current_contig].append(inv_cluster)
        else:
            inv_cluster.score = 0
            inv_not_to_confirm.append(inv_cluster)

    inputs = []
    for contig in sorted(inv_to_confirm_dict.keys()):
        inputs.append((inv_to_confirm_dict[contig], "inversion", left_aln, right_aln, full_aln, full_reads_path, options.genome, parameters))
    results = pool.starmap(confirm_clusters_in_contig, inputs)
    inversion_evidence_clusters = list(itertools.chain.from_iterable(results)) + inv_not_to_confirm

    ############################
    # Write confirmed clusters #
    ############################
    logging.info("Write confirmed evidence clusters..")
    deletion_evidence_output = open(options.working_dir + '/evidences/del_confirmed.bed', 'w')
    insertion_evidence_output = open(options.working_dir + '/evidences/ins_confirmed.bed', 'w')
    inversion_evidence_output = open(options.working_dir + '/evidences/inv_confirmed.bed', 'w')

    for cluster in deletion_evidence_clusters:
        print(cluster.get_bed_entry(), file=deletion_evidence_output)
    for cluster in insertion_evidence_clusters:
        print(cluster.get_bed_entry(), file=insertion_evidence_output)
    for cluster in inversion_evidence_clusters:
        print(cluster.get_bed_entry(), file=inversion_evidence_output)

    deletion_evidence_output.close()
    insertion_evidence_output.close()
    inversion_evidence_output.close()

    #################
    # Dump obj file #
    #################
    evidence_clusters = deletion_evidence_clusters, insertion_evidence_clusters, inversion_evidence_clusters, tandem_duplication_evidence_clusters, insertion_from_evidence_clusters, completed_translocations
    evidences_file = open(options.working_dir + '/sv_confirmed_evidences.obj', 'wb')
    logging.info("Storing confirmed evidence clusters into sv_confirmed_evidences.obj..")
    pickle.dump(evidence_clusters, evidences_file)
    evidences_file.close()

if __name__ == "__main__":
    sys.exit(main())
