import codecs 
import time
import datetime
import operator
import sys
import os
import codecs # for utf8
import string
import copy
import math
from latexTable import MakeLatexTable

# Feb 19 2024. [WF] Added explanatory comment line 237

verboseflag = False

# ---------------------------------------------------------#

# A word that we are analyzing has a Profiles. Its m_word is the word, naturally.
# It has a dict whose key is the iteration number, and whose value is a profile
class Profiles:
	def __init__ (self, word):
		self.m_word =  word
		self.m_profiles = dict()
	def add_profile (self, iteration, profile):
		if not iteration in self.m_profiles:
			self.m_profiles[iteration] = profile
	def display(self):
		result = ""
		for iter in self.m_profiles.keys():
			result += "iteration:  " + str(iter) + "\n" + self.m_profiles[iter].display() +  "\n"
		return result
	
# A profile is mostly a dict. 
# That dict is one whose key is a string, like "t he" (a parse) and whose value is an integer, the count of that parsing ("t he") in this iteration.\
class Profile:
    def __init__(self):
        self.m_parses = dict()
    def add_parse(self, parse):		
        if not parse in self.m_parses: 
            self.m_parses[parse] = 0
        self.m_parses[parse] += 1	
    def display(self):
        result = ""
        for parse, count in self.m_parses.items():
           result += parse + ":"   + str(count) + "\n"
        return result

# ---------------------------------------------------------#
def corpus_slice_from_piece_number(string, breakpoint_list, piece_number):
		start_position = breakpoint_list[piece_number]
		if piece_number == len(breakpoint_list) - 1:
			#print (53, string, "start position", start_position, string[start_position] )
			return  string[start_position]
		else:
			end_position = breakpoint_list[piece_number + 1]
			length = end_position - start_position
			#print (58, string, "start position", start_position, string[start_position], "end position", end_position, "length", length)
			return  string[start_position:end_position]

# ---------------------------------------------------------#
 
 
# not used
def breakpoints2chunks(breakpoint_list):
	chunks = list()
	for i in range(1, len(breakpoint_list)):
		chunks.append(breakpoint_list[i]-breakpoint_list[i-1])
	return chunks

# not used
def chunks2breakpoints(chunk_list):
	breakpoint_list = list()
	breakpoint_list.append(0)
	point = 0
	for i in range(len(chunk_list)):
		point += chunk_list[i]
		breakpoint_list.append(point)
	return breakpoint_list

def read_glossary (infile, glossary):
    locations = list()
    while (True):
        line = infile.readline()
        if not line:
            break
        if line.startswith( target_word ):
            lines_and_positions = infile.readline()
            lines_and_positions = lines_and_positions.split(" ")
            while (lines_and_positions):
                line_and_position = lines_and_positions.pop(0)
                pieces = line_and_position.split(":")
                if len(pieces) < 2:
                    break;
                line, position = line_and_position.split(":")
                line = line.strip()
                position = position.strip()			
                locations.append((line,position))
            return locations
def detect_number_of_iterations(parsings_file):
	count = 0
	parsings_file.seek(0) # reset to beginning of file
	while (True):
		line = parsings_file.readline()
		if line[:19] == "#current_iteration#":
			count += 1
		if not line:
			break	
	parsings_file.seek(0)
	return count;
 
# ---------------------------------------------------------#
 
# ---------------------------------------------------------#
# Given a position in a string, return the piece number of the breakpoint list that it is in
def position2chunk_number (breakpoint_list, position):
		position = int(position)
		for n in  range(len(breakpoint_list)):
			if breakpoint_list[n] == position:
				return n;
			if breakpoint_list[n] > position:
				return n-1
		return -1	
# ---------------------------------------------------------#
# takes breakpoint list and two breakpoint indexes, and gives a string of letters
def corpus_slice_sequence(corpus_line, breakpoint_list, first_piece_number, last_piece_number):
		resulting_slice = ""
		for n in range(first_piece_number, last_piece_number +1):
			if len(resulting_slice) != 0:
				resulting_slice += " "			 
			chunk = corpus_slice_from_piece_number(corpus_line, breakpoint_list, n  )
			resulting_slice += chunk	
		return resulting_slice	 
# ---------------------------------------------------------#
# not used
def piece_number2slice(corpus_line, breakpoints, chunk_number):
	start_position = breakpoints[chunk_number]
	end = breakpoints[chunk_number+1]
	return corpus_line[start_position:end]


# ---------------------------------------------------------#
# takes word, and provides a string
# which shows how that True Parse (i.e., the target word) is analyzed in the parse
# provided by "breakpoints".
def find_parse_of_target_word(corpus_line, computed_breakpoints, target_word, start_point):
		start_chunk_number = position2chunk_number(computed_breakpoints, start_point)
		endpoint = int(start_point) + len(target_word) - 1
		end_chunk_number = position2chunk_number( computed_breakpoints, endpoint)
		return corpus_slice_sequence(corpus_line, computed_breakpoints, start_chunk_number, end_chunk_number)
# ---------------------------------------------------------#
def get_true_breakpoints(corpus_file, line_number):
	corpus_file.seek(0);
	line_number = str(line_number)
	while (True):
		line = corpus_file.readline()
		if line== "#@#":
			return list()
		if line.startswith( line_number ):
			string_of_breakpoints = corpus_file.readline()
			breakpoints = string_of_breakpoints.split()
			return  breakpoints
	print (905)
	return list()
# ---------------------------------------------------------# 
def skip_to_next_iteration (infile,  ):
	while(True):
		line = infile.readline()
		if not line:
			return -1
		if line[:9] == "#current_":
			return  
	return -1			
# ---------------------------------------------------------# 
def get_corpus_line(corpus_file, line_number):
	#corpus_file.seek(0)
	line_number = str(line_number)
	while (True):
		line=corpus_file.readline()
		if not line:
			return
		if line== "#@#":
			return ""
		pieces = line.split(":",1)
		if pieces[0] == line_number :
			line =  pieces[1].strip()
			true_break_points = corpus_file.readline();
			return line, true_break_points
# ---------------------------------------------------------# 
def list_of_strings2ints(this_list):
	result = list()
	for item in this_list:
		if item.isdigit():
			result.append(int(item))
	return result
# ---------------------------------------------------------# 
def get_breakpoints(infile_parsings, line_number, previous_computed_breakpoints):
	#print (896, "get breakpoints for line ", line_number)
	while (True):
		current_line = infile_parsings.readline()
		if current_line[:8] == "#current":
			return "not found"
		if not current_line:
			return list()
		current_line = current_line.split(':')
		#print (908, "current line ", current_line)
		temp_line_number = int(current_line[0].strip())		
		if (int(temp_line_number) == int(line_number)):			 
			return list_of_strings2ints(current_line[1].split(' ')) 
 

# ---------------------------------------------------------# 

def analyze_history(corpus_file, infile_parsings, locations, target_word, profiles, number_of_iterations):
	infile_parsings.readline()
	current_line_number_in_parsings_file = 0
	for iteration_number in range(number_of_iterations):
		print ("iteration number ", iteration_number)
		corpus_file.seek(0)
		profile = Profile()
		profiles.add_profile(iteration_number, profile) 
		computed_breakpoints = list()
		previous_line_number = -1
		for n in range(len(locations)):
			line_number, start_point = locations[n] 	
			if not line_number == previous_line_number:
				corpus_line, true_breakpoints = get_corpus_line(corpus_file, line_number)	 # fine
				computed_breakpoints = get_breakpoints(infile_parsings, line_number, computed_breakpoints)
			parse = find_parse_of_target_word(corpus_line, computed_breakpoints, target_word, start_point)
			profile.add_parse(parse)
			previous_line_number = line_number
		skip_to_next_iteration (infile_parsings)





################################################################################
# Given a target word, this code prints a history of the target word and other 
# parses of the same text over all iterations of the Lexicon. 
#
# NB: Before running this code, the Lexicon should already have been generated
#     and analyzed -- with information about hte relevant corpus already printed
#     to a number of outfiles (see wordbreaker.py). 
#
# The user should provide:
#   - datadirectory -- path the to the corpus file
#
#   - corpusfile -- name of the corpus file
#
#   - prefix -- a name used to identify the different outfiles that a run 
#     of this code will generate
#
# The user may also specify:
#   - numberofcycles -- the number of times the model should generate new 
#     word-candidates
#
#   - howmanycandidatesperiteration -- the number of candidates the model should
#     generate during each iteration 
#
# Running this code will print information to the following outfile:
#
#   <prefix>_analysis_.txt
#       - for each iteration, the different parses of the target word and their
#         counts.
#
# [WF]


target_word = "history"

directory 			= "../../data/english-browncorpus/wordbreaking/"
outdirectory        = directory
prefix              = "wordbreaker_brown_corpus_"
num_iters 			= "50"
new_words_per_iter  = "100"
corpus_filename     = directory + prefix + num_iters + "_iters_" + new_words_per_iter + "_new_per_iteration"  + "_processed_corpus.txt"
parsings_filename 	= directory + prefix + num_iters + "_iters_" + new_words_per_iter + "_new_per_iteration"  + "_iterated_parsings" + ".txt" 
outfilename         = directory + prefix + num_iters + "_iters_" + new_words_per_iter + "_new_per_iteration"  +  "_analysis_" + target_word + ".txt"
glossary_filename   = directory + prefix + num_iters + "_iters_" + new_words_per_iter + "_new_per_iteration"  + "_glossary" + ".txt"

g_encoding = "utf8"
if g_encoding == "utf8":
	print ("utf8")
	corpus_file = codecs.open(corpus_filename, "r", encoding = 'utf-8')
	parsings_file = codecs.open(parsings_filename, "r", encoding = 'utf-8')
	outfile = codecs.open(outfilename, "w", encoding = 'utf-8')
	glossary_file = open (glossary_filename, "r", encoding = 'utf-8')
 
else:
	print (1002)
	corpus_file = codecs.open(corpus_filename, "r")
	parsings_file = codecs.open(parsings_filename, "r")
	outfile = codecs.open(outfilename, "w")
	glossary_file = codecs.open(glossary_filename, "r")
 
profiles = Profiles(target_word)
number_of_iterations = detect_number_of_iterations(parsings_file)
locations = list()
locations = read_glossary(glossary_file, locations)
print (960, parsings_file.readline())
analyze_history(corpus_file, parsings_file, locations, target_word,profiles, number_of_iterations) 

print (profiles.display(), file = outfile )

 
 

