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

# Feb 19 2024: [WF] added docstrings for key methods in Lexicon class, and explanatory comment line 906

verboseflag = False

# Jan 6: added precision and recall.
# A word that we are analyzing has a Profiles. Its m_word is the word, naturally.
class Profiles:
	def __init__ (self, word):
		self.m_word =  word
		self.m_profile =  list()
 
# A profile is mostly a dict: m_iterations. Its key is a number (the iteration number), its value is a dict.
# That dict is one whose key is a string, like "t he" and its value is an integer, the count of that parsing ("t he") in this iteration.
class Profile:
	def __init__(self):
		self.m_iterations = dict()
	def append(self, profile, iteration):		
		self.m_iterations[iteration] = dict()
		# the dict has sequences of words with spaces in between; its value is a count.

#---------------------------------------------------------
class LexiconEntry:
	def __init__(self, key = "", count = 0):
		self.m_Key = key
		self.m_Count = count
		self.m_Frequency= 0.0
		self.m_CountRegister = list()
		
		
	def ResetCounts(self, current_iteration):
		if len(self.m_CountRegister) > 0:
			last_count = self.m_CountRegister[-1][1]
			if self.m_Count != last_count:
				self.m_CountRegister.append((current_iteration-1, self.m_Count))
		else:
			self.m_CountRegister.append((current_iteration, self.m_Count))
		self.m_Count = 0
	def Display(self, outfile):
		print  ("%-20s" % self.m_Key, file = outfile)
		for iteration_number, count in self.m_CountRegister:
			print ("%6i %10s" % (iteration_number, "{:,}".format(count)), file = outfile)
# ---------------------------------------------------------#
class Lexicon:
	def __init__(self):
		self.m_Profiles = Profiles("")
		self.m_LetterDict=dict() 
		self.m_LetterPlog = dict()
		self.m_EntryDict = dict()   # maps entries in the lexicon (strings) to the corresponding lexicon entry objects [WF]
		self.m_TrueDictionary = dict()
		self.m_DictionaryLength = 0   #in bits! Check this is base 2, looks like default base in python
		self.m_Corpus 	= list()
		self.m_SizeOfLongestEntry = 0
		self.m_CorpusCost = 0.0
		self.m_Glossary = dict()
		self.m_ParsedCorpus = list()
		self.m_NumberOfHypothesizedRunningWords = 0
		self.m_NumberOfTrueRunningWords = 0
		self.m_TrueBreakPointList = list()
		self.m_DeletionList = list()  # these are the words that were nominated and then not used in any line-parses *at all*.
		self.m_DeletionDict = dict()  # They never stop getting nominated.
		self.m_Break_based_RecallPrecisionHistory = list()
		self.m_Token_based_RecallPrecisionHistory = list()
		self.m_Type_based_RecallPrecisionHistory = list()
		self.m_DictionaryLengthHistory = list()
		self.m_CorpusCostHistory = list()
		self.g_encoding = ""
	# ---------------------------------------------------------#
	# ---------------------------------------------------------#
	def AddEntry(self,key,count):
		this_entry = LexiconEntry(key,count)
		self.m_EntryDict[key] = this_entry
		if len(key) > self.m_SizeOfLongestEntry:
			self.m_SizeOfLongestEntry = len(key)
	# ---------------------------------------------------------#	
	# Found bug here July 5 2015: important, don't let it remove a singleton letter! John
	def FilterZeroCountEntries(self, iteration_number):
        """ Removes entries in the lexicon with count of 0 (but not singletons letters). [WF]"""
		for key, entry in list(self.m_EntryDict.items()):
			if len(key) == 1:
				entry.m_Count = 1
				continue
			if entry.m_Count == 0:
				self.m_DeletionList.append((key, iteration_number))
				self.m_DeletionDict[key] = 1
				self.m_EntryDict.pop(key)
				print ("Excluding this bad candidate: ", key)
	# ---------------------------------------------------------#
	def ReadCorpus(self, infilename):
        """ 
        Reads corpus from file and intitalizes lexicon. 
        
        When initialized, a the entries of a lexicon consist of the letters in 
        the alphabet of the corpus. 
        
        [WF]
        """
		print ("Name of data file: ", infilename)
		if not os.path.isfile(infilename):
			print ("Warning: ", infilename, " does not exist.")
		if self.g_encoding == "utf8":
			infile = codecs.open(infilename, encoding = 'utf-8')
		else:
			infile = open(infilename) 	 
		self.m_Corpus = infile.readlines() # bad code if the corpus is very large -- but then we won't use python.
		for line in self.m_Corpus:			 		 
			for letter in line:
				if letter not in self.m_EntryDict:
					this_lexicon_entry = LexiconEntry()
					this_lexicon_entry.m_Key = letter
					this_lexicon_entry.m_Count = 1
					self.m_EntryDict[letter] = this_lexicon_entry					 
				else:
					self.m_EntryDict[letter].m_Count += 1
		self.m_SizeOfLongestEntry = 1	
		self.ComputeDictFrequencies()
	# ---------------------------------------------------------#
	def ReadBrokenCorpus(self, infilename, numberoflines= 0):
        """ 
        Reads broken corpus from file and intitalizes lexicon.
        
        When initialized, the entries of a lexicon consist of the letters in 
        the alphabet of the corpus. 
        
        From the original, word-separated, corpus this method records: 
            - the number of words,
            - each word, 
            - and its count
        to relevant attributes in Lexicon class. 

        Because information about the state of the original corpus is recorded, 
        our parse's precision and recall with respects to the original corpus
        may be calculated later. 

        Optionally, this methodtakes second argument which specifies the number 
        of lines from the original corpus which should be read. 
        [WF]
        """
		print ("Name of data file: ", infilename)
		if not os.path.isfile(infilename):
			print ("Warning: ", infilename, " does not exist.")
		if self.g_encoding == "utf8":
			infile = codecs.open(infilename, encoding = 'utf-8')
		else:
			infile = open(infilename) 	 
		 
		rawcorpus_list = infile.readlines() # bad code if the corpus is very large -- but then we won't use python.
		lineno = -1
		for line in rawcorpus_list:					 	 
			this_line = ""
			breakpoint_list = list()
			breakpoint_list.append(0)
			line = line.replace('.', ' .').replace('?', ' ?')
			line_list = line.split()
			if len(line_list) <=  1:
				continue			
			lineno += 1	 	 
			for word in line_list:
				self.m_NumberOfTrueRunningWords += 1
				if word not in self.m_TrueDictionary:
					self.m_TrueDictionary[word] = 1
					#print ("125 true dict", word)
				else:
					#print (word)
					self.m_TrueDictionary[word] += 1
				startpoint = len(this_line)
				this_line += word
				breakpoint_list.append(len(this_line))
				if  word not in self.m_Glossary:
					self.m_Glossary[word]= list()
				self.m_Glossary[word].append((lineno, startpoint)) 
				#print (word, self.m_Glossary[word])	
			self.m_Corpus.append(this_line)         ### removed space [WF]
			self.m_TrueBreakPointList.append(breakpoint_list)
			for letter in line:
				if letter not in self.m_EntryDict:
					this_lexicon_entry = LexiconEntry()
					this_lexicon_entry.m_Key = letter
					this_lexicon_entry.m_Count = 1
					self.m_EntryDict[letter] = this_lexicon_entry					 
				else:
					self.m_EntryDict[letter].m_Count += 1	
				if letter not in self.m_LetterDict:
					self.m_LetterDict[letter] = 1
				else:
					self.m_LetterDict[letter] += 1		 
			if numberoflines > 0 and len(self.m_Corpus) > numberoflines:
				break		 
			
		print ("number of lines", len(self.m_Corpus))
		print ("number of breakpoint lines", len(self.m_TrueBreakPointList))
		self.m_SizeOfLongestEntry = 1	
		self.ComputeDictFrequencies()
# ---------------------------------------------------------#
	def PrintBrokenCorpus (self, outfile, outfile_glossary ):
		# Two parts to this output:
		# First, a line for each line in the input corpus but with all spaces removed;
		# and also a list of the break positions for the preceding line.
		# Second, a glossary, which is a dict (one for each real word)
		# which is printed as a words, the keys of the dict;
		# Each word is a single line,  of line number plus initial starting point for
		#	 each real word in the corpus
		# Sept 17 2023 made the list into a string....
		lineno = 0
		for line in self.m_Corpus:
			print (lineno, ":", line, sep='', file = outfile)  
			newlist = list()
			for number in self.m_TrueBreakPointList[lineno]:
				newlist.append (str(number))
			#print ("\n", 191, ' '.join(newlist) )
			print ( ' '.join(newlist), file = outfile)		 
			lineno += 1
		#print ("#@#", file = outfile)
	 
		for word, hits in sorted(self.m_Glossary.items()):
			print (word, self.m_TrueDictionary[word], file = outfile_glossary)
			for item in self.m_Glossary[word]:
				print (item[0], ':', item[1], ' ',  file = outfile_glossary, end='', sep='')
			print (file=outfile_glossary)
		#outfile.close()
 # ---------------------------------------------------------#
	def ComputeDictFrequencies(self):
        """For each entry in the lexicon, compute its frequency of occurance. [WF]"""
		TotalCount = 0
		for (key, entry) in self.m_EntryDict.items():
			TotalCount += entry.m_Count
		for (key, entry) in self.m_EntryDict.items():
			entry.m_Frequency = entry.m_Count/float(TotalCount)
		TotalCount = 0
		for (letter, count) in self.m_LetterDict.items():
			TotalCount += count
		for (letter, count) in self.m_LetterDict.items():
			self.m_LetterDict[letter] = float(count)/float(TotalCount)
			self.m_LetterPlog[letter] = -1 * math.log(self.m_LetterDict[letter])
# ---------------------------------------------------------#
	# added july 2015 john
	def ComputeDictionaryLength(self):
        """ 
        Computes the dictionary length — which is the sum of individual word
        lengths. Each individual word length is the sum of the plogs of the 
        frequency of its letters. 
        
        The length of the dictionary is saved in the relevant atribute of the 
        Lexicon class. 
        [WF]
        """
		DictionaryLength = 0
		for word in self.m_EntryDict:
			wordlength = 0
			letters = list(word)
			for letter in letters:
				wordlength += self.m_LetterPlog[letter]
			DictionaryLength += wordlength
		self.m_DictionaryLength = DictionaryLength
		self.m_DictionaryLengthHistory.append(DictionaryLength)
			 
# ---------------------------------------------------------#
	def ParseCorpus(self, outfile, outfile_parsings, current_iteration):
        """ 
        Parse corpus:
            - break the corpus into chunks (highest probability parse)
            - recalculate counts of each word entry in lexicon
            - tabulate number of hypothesized running words
        
        Computes corpus cost and dictionary length (i.e. the compression of the 
        data and length of this particular hypothesized lexicon). 

        The sum of these — the copus cost and dictionary length — is the description
        length, which is what is minimized in MDL (Minimum Description Length analysis.)
        [WF]
        """
		print  ("#current_iteration# ", current_iteration, file = outfile_parsings )
		#print ("current interation", current_iteration)
		self.m_ParsedCorpus = list()
		self.m_CorpusCost = 0.0	
		self.m_NumberOfHypothesizedRunningWords = 0
		#total_word_count_in_parse = 0	 
		for word, lexicon_entry in self.m_EntryDict.items():
			lexicon_entry.ResetCounts(current_iteration)
		line_number = 0
		for line in self.m_Corpus:	
			#print (line)
			chunks = list()
			parsed_line,bit_cost = 	self.ParseWord(line, outfile)	
			self.m_ParsedCorpus.append(parsed_line)
			self.m_CorpusCost += bit_cost
			for word in parsed_line:
				length = len(word)
				chunks.append(length)
				self.m_EntryDict[word].m_Count +=1
				self.m_NumberOfHypothesizedRunningWords += 1
			breakpoint_list = chunks2breakpoints(chunks) 
			print (line_number, ':', sep='', file = outfile_parsings, end = '')
			print (*breakpoint_list, sep=' ', file = outfile_parsings)
			line_number+= 1
		self.FilterZeroCountEntries(current_iteration)
		self.ComputeDictFrequencies()
		self.ComputeDictionaryLength()
		print ("\nCorpus     cost: ", "{:,}".format(int(self.m_CorpusCost)))
		print ("Dictionary cost: ", "{:,}".format(int(self.m_DictionaryLength)))
		sum = int(self.m_CorpusCost + self.m_DictionaryLength)
		print   ("Total      cost: ", "{:,}".format(sum))
		print (("\nCorpus cost: ", "{:,}".format(self.m_CorpusCost)), file = outfile)
		print ("Dictionary cost: ", "{:,}".format(self.m_DictionaryLength), file = outfile)
		print ("Total description length: ", "{:,}".format(self.m_CorpusCost + self.m_DictionaryLength), file = outfile)
		return  
# ---------------------------------------------------------#		 	 
	def PrintParsedCorpus(self,outfile):
        """ Print's parsed corpus, line-by-line. [WF]"""
		for line in self.m_ParsedCorpus:
			PrintList(line,outfile)		
# ---------------------------------------------------------#
	
# ---------------------------------------------------------#
	def ParseWord(self, word, outfile):
        """
        Breaks a line of a corpus into chunks using outerscan / innerscan parse 
        technique — see below. This method chooses the highest probability parse. 

        Returns (as tuple):
            - Parsed line, broken into chunks
            - bit cost of parsing line (i.e. its compression of the data)
        [WF]
        """
		wordlength = len(word)
		Parse = dict()	 
		Piece = ""	
		LastChunk = ""		 
		BestCompressedLength = dict()
		BestCompressedLength[0] = 0
		CompressedSizeFromInnerScanToOuterScan = 0.0
		LastChunkStartingPoint = 0
		# <------------------ outerscan -----------><------------------> #
		#                  ^---starting point
		# <----prefix?----><----innerscan---------->
		#                  <----Piece-------------->
		if verboseflag: print >>outfile, "\nOuter\tInner"
		if verboseflag: print >>outfile, "scan:\tscan:\tPiece\tFound?"
		for outerscan in range(1,wordlength+1):  
			Parse[outerscan] = list()
			MinimumCompressedSize= 0.0
			startingpoint = 0
			if outerscan > self.m_SizeOfLongestEntry:
				startingpoint = outerscan - self.m_SizeOfLongestEntry
			for innerscan in range(startingpoint, outerscan):
				if verboseflag: print >>outfile,  "\n %3s\t%3s  " %(outerscan, innerscan),				 
				Piece = word[innerscan: outerscan]	 
				if verboseflag: print >>outfile, " %5s"% Piece, 			 
				if Piece in self.m_EntryDict:		
					if verboseflag: print >>outfile,"   %5s" % "Yes.",		 
					CompressedSizeFromInnerScanToOuterScan = -1 * math.log( self.m_EntryDict[Piece].m_Frequency )				
					newvalue =  BestCompressedLength[innerscan]  + CompressedSizeFromInnerScanToOuterScan  
					if verboseflag: print >>outfile,  " %7.3f bits" % (newvalue), 
					if  MinimumCompressedSize == 0.0 or MinimumCompressedSize > newvalue:
						MinimumCompressedSize = newvalue
						LastChunk = Piece
						LastChunkStartingPoint = innerscan
						if verboseflag: print >>outfile,  " %7.3f bits" % (MinimumCompressedSize), 
				else:
					if verboseflag: print >>outfile,"   %5s" % "No. ",
			BestCompressedLength[outerscan] = MinimumCompressedSize
			if LastChunkStartingPoint > 0:
				Parse[outerscan] = list(Parse[LastChunkStartingPoint])
			else:
				Parse[outerscan] = list()
			if verboseflag: print >>outfile, "\n\t\t\t\t\t\t\t\tchosen:", LastChunk,
			Parse[outerscan].append(LastChunk)

			#if len(LastChunk) == 0:
			#	print >>outfile, "line 212", word, Parse[outerscan]		 
			#	print "line 212", word, "outerscan:", outerscan, "Last chunk:", LastChunk, Parse[outerscan]		

		if verboseflag: 
			PrintList(Parse[wordlength], outfile)
		bitcost = BestCompressedLength[outerscan] 
		return (Parse[wordlength],bitcost)
# ---------------------------------------------------------#
	def GenerateCandidates(self, howmany, outfile):
        """
        Generates candidate words. 

        Candidate words are formed by combining existing words in the lexicon which
        appear adjacently in the parsed corpus. This method chooses a specified number
        of the highest frequency candidate words. 

        Args:
            - howmany: K, the number of candidates to generate. We usually take K = 25
            - outfile: the file to which relevant information should be printed

        Returns:
            - list of nominated words
        [WF]
        """
		Nominees = dict()
		NomineeList = list()
		for parsed_line in self.m_ParsedCorpus:	 
			for wordno in range(len(parsed_line)-1):
				candidate = parsed_line[wordno] + parsed_line[wordno + 1]				 		 
				if candidate in self.m_EntryDict:					 
					continue										 
				if candidate in Nominees:
					Nominees[candidate] += 1
				else:
					Nominees[candidate] = 1					 
		EntireNomineeList = sorted(Nominees.items(),key=operator.itemgetter(1),reverse=True)
		for nominee, count in EntireNomineeList:
			if nominee  in self.m_DeletionDict:				 
				continue
			else:				 
				NomineeList.append((nominee,count))
			if len(NomineeList) == howmany:
				break
		#print "Nominees:"
		latex_data= list()
		latex_data.append("piece   count   status")
		for nominee, count in NomineeList:
			self.AddEntry(nominee,count)
			print ("%20s   %8i" %(nominee, count))
			latex_data.append(nominee +  "\t" + "{:,}".format(count) )
		MakeLatexTable(latex_data,outfile)
		self.ComputeDictFrequencies()
		return NomineeList

# ---------------------------------------------------------#
	def Expectation(self):
		self.m_NumberOfHypothesizedRunningWords = 0
		for this_line in self.m_Corpus:
			wordlength = len(this_line)
			ForwardProb = dict()
			BackwardProb = dict()
			Forward(this_line,ForwardProb) 
			Backward(this_line,BackwardProb)
			this_word_prob = BackwardProb[0]
			
			if WordProb > 0:          
				for nPos in range(wordlength):
					for End in range(nPos, wordlength-1):
						if End- nPos + 1 > self.m_SizeOfLongestEntry:
							continue
						if nPos == 0 and End == wordlength - 1:
							continue
						Piece = this_line[nPos, End+1]
						if Piece in self.m_EntryDict:
							this_entry = self.m_EntryDict[Piece]
							CurrentIncrement = ((ForwardProb[nPos] * BackwardProb[End+1])* this_entry.m_Frequency ) / WordProb
							this_entry.m_Count += CurrentIncrement
							self.m_NumberOfHypothesizedRunningWords += CurrentIncrement			



# ---------------------------------------------------------#
	def Maximization(self):
		for entry in self.m_EntryDict:
			entry.m_Frequency = entry.m_Count / self.m_NumberOfHypothesizedRunningWords

# ---------------------------------------------------------#
	def Forward (self, this_line,ForwardProb):
		ForwardProb[0]=1.0
		for Pos in range(1,Length+1):
			ForwardProb[Pos] = 0.0
			if (Pos - i > self.m_SizeOfLongestEntry):
				break
			Piece = this_line[i,Pos+1]
			if Piece in self.m_EntryDict:
				this_Entry = self.m_EntryDict[Piece]
				vlProduct = ForwardProb[i] * this_Entry.m_Frequency
				ForwardProb[Pos] = ForwardProb[Pos] + vlProduct
		return ForwardProb

# ---------------------------------------------------------#
	def Backward(self, this_line,BackwardProb):
		
		Last = len(this_line) -1
		BackwardProb[Last+1] = 1.0
		for Pos in range( Last, Pos >= 0,-1):
			BackwardProb[Pos] = 0
			for i in range(Pos, i <= Last,-1):
				if i-Pos +1 > m_SizeOfLongestEntry:
					Piece = this_line[Pos, i+1]
					if Piece in self.m_EntryDict[Piece]:
						this_Entry = self.m_EntryDict[Piece]
						if this_Entry.m_Frequency == 0.0:
							continue
						vlProduct = BackwardProb[i+1] * this_Entry.m_Frequency
						BackwardProb[Pos] += vlProduct
		return BackwardProb


# ---------------------------------------------------------#		
	def PrintLexicon(self, outfile):
        """
        Prints (alphabetically):
            - members of the lexicon
            - their counts over each iteration they were included in the lexicon 

        Also:
            - deleted candidate words
            - the iteration when they were deleted    
        [WF]
        """
		for key in sorted(self.m_EntryDict.keys()):			 
			self.m_EntryDict[key].Display(outfile) 
		for iteration, key in self.m_DeletionList:
			print ( iteration, key, file=outfile)

	def	PrintSimpleLexicon(self, outfile_simple_lexicon):
		for key in sorted(self.m_EntryDict.keys()):
			print (key,file=outfile_simple_lexicon)

 

# ---------------------------------------------------------#
	def RecallPrecision(self, iteration_number, outfile,total_word_count_in_parse):
		"""
        Calculates and prints the precision and recall of the current parse, 
        relative to the true state of the corpus. 

        Break-based, token-based, and type-based precision + recall values are 
        calculated.
        [WF]
        """
		total_true_positive_for_break = 0
		total_number_of_hypothesized_words = 0
		total_number_of_true_words = 0
		for linenumber in range(len(self.m_TrueBreakPointList)):		 
			truth = list(self.m_TrueBreakPointList[linenumber])			 
			if len(truth) < 2:
				print >>outfile, "Skipping this line:", self.m_Corpus[linenumber]
				continue
			number_of_true_words = len(truth) -1				
			hypothesis = list()  					 
			hypothesis_line_length = 0
			accurate_word_discovery = 0
			true_positive_for_break = 0
			word_too_big = 0
			word_too_small = 0
			real_word_lag = 0
			hypothesis_word_lag = 0
			 
			for piece in self.m_ParsedCorpus[linenumber]:
				hypothesis_line_length += len(piece)
				hypothesis.append(hypothesis_line_length)
			number_of_hypothesized_words = len(hypothesis) 			 

			# state 0: at the last test, the two parses were in agreement
			# state 1: at the last test, truth was # and hypothesis was not
			# state 2: at the last test, hypothesis was # and truth was not
			pointer = 0
			state = 0
			while (len(truth) > 0 and len(hypothesis) > 0):
				 
				next_truth = truth[0]
				next_hypothesis  = hypothesis[0]
				if state == 0:
					real_word_lag = 0
					hypothesis_word_lag = 0					
									
					if next_truth == next_hypothesis:
						pointer = truth.pop(0)
						hypothesis.pop(0)
						true_positive_for_break += 1
						accurate_word_discovery += 1
						state = 0
					elif next_truth < next_hypothesis:						 
						pointer = truth.pop(0)
						real_word_lag += 1
						state = 1
					else: #next_hypothesis < next_truth:						 
						pointer = hypothesis.pop(0)
						hypothesis_word_lag = 1
						state = 2
				elif state == 1:
					if next_truth == next_hypothesis:
						pointer = truth.pop(0)
						hypothesis.pop(0)
						true_positive_for_break += 1
						word_too_big += 1						
						state = 0
					elif next_truth < next_hypothesis:
						pointer = truth.pop(0)
						real_word_lag += 1
						state = 1 #redundantly
					else: 
						pointer = hypothesis.pop(0)
						hypothesis_word_lag += 1
						state = 2
				else: #state = 2
					if next_truth == next_hypothesis:
						pointer = truth.pop(0)
						hypothesis.pop(0)
						true_positive_for_break += 1
						word_too_small +=1
						state = 0
					elif next_truth < next_hypothesis:
						pointer = truth.pop(0)
						real_word_lag += 1
						state = 1
					else:
						pointer = hypothesis.pop(0)
						hypothesis_word_lag += 1
						state =2 						
			 			 
 
	
					
			precision = float(true_positive_for_break) /  number_of_hypothesized_words 
			recall    = float(true_positive_for_break) /  number_of_true_words 			
			 		
			total_true_positive_for_break += true_positive_for_break
			total_number_of_hypothesized_words += number_of_hypothesized_words
			total_number_of_true_words += number_of_true_words


		 



		# the following calculations are precision and recall *for breaks* (not for morphemes)

		formatstring = "%30s %6.4f %12s %6.4f"
		total_break_precision = float(total_true_positive_for_break) /  total_number_of_hypothesized_words 
		total_break_recall    = float(total_true_positive_for_break) /  total_number_of_true_words 	
		self.m_CorpusCostHistory.append( self.m_CorpusCost)
		self.m_Break_based_RecallPrecisionHistory.append((iteration_number,  total_break_precision,total_break_recall))
		print (formatstring %( "Break based Word Precision", total_break_precision, "recall", total_break_recall))
		print  (formatstring %( "Break based Word Precision", total_break_precision, "recall", total_break_recall), file=outfile)
		
		# Token_based precision for word discovery:
		


		if (True):
			true_positives = 0
			for (word, this_words_entry) in self.m_EntryDict.items():
				if word in self.m_TrueDictionary:
					true_count = self.m_TrueDictionary[word]
					these_true_positives = min(true_count, this_words_entry.m_Count)
				else:
					these_true_positives = 0
				true_positives += these_true_positives
			word_recall = float(true_positives) / self.m_NumberOfTrueRunningWords
			word_precision = float(true_positives) / self.m_NumberOfHypothesizedRunningWords
			self.m_Token_based_RecallPrecisionHistory.append((iteration_number,  word_precision,word_recall))

			print  (formatstring %( "Token_based Word Precision", word_precision, "recall", word_recall), file=outfile)
			print  (formatstring %( "Token_based Word Precision", word_precision, "recall", word_recall))
 

		# Type_based precision for word discovery:
		if (True):
			true_positives = 0
			for (word, this_words_entry) in self.m_EntryDict.items():
				if word in self.m_TrueDictionary:
					true_positives +=1
			word_recall = float(true_positives) / len(self.m_TrueDictionary)
			word_precision = float(true_positives) / len(self.m_EntryDict)
			self.m_Type_based_RecallPrecisionHistory.append((iteration_number,  word_precision,word_recall))
			
			#print >>outfile, "\n\n***\n"
#			print "Type_based Word Precision  %6.4f; Word Recall  %6.4f" %(word_precision ,word_recall)
			print  (formatstring %( "Type_based Word Precision", word_precision, "recall", word_recall), file=outfile)
			print  (formatstring %( "Type_based Word Precision", word_precision, "recall", word_recall))

# ---------------------------------------------------------#
	def PrintRecallPrecision(self,outfile):	
		print  ("\t\t\tBreak\t\tToken-based\t\tType-based", file = outfile)
		print  ("\t\t\tprecision\trecall\tprecision\trecall\tprecision\trecall", file=outfile)
		for iterno in (range(numberofcycles-1)):
			print ("printing iterno", iterno)
			(iteration, p1,r1) = self.m_Break_based_RecallPrecisionHistory[iterno]
			(iteration, p2,r2) = self.m_Token_based_RecallPrecisionHistory[iterno]
			(iteration, p3,r3) = self.m_Type_based_RecallPrecisionHistory[iterno]
			cost1 = int(self.m_DictionaryLengthHistory[iterno])
			cost2 = int(self.m_CorpusCostHistory[iterno] )
			#print >>outfile,"%3i\t%8.3f\t%8.3f\t%8.3f\t%8.3f\t%8.3f\t%8.3f" %(iteration, r1,p1,r2,p2,r3,p3)
			print  ((iteration,"\t",cost1, "\t", cost2, "\t", p1,"\t",r1,"\t",p2,"\t",r2,"\t",p3,"\t",r3), file=outfile)
# ---------------------------------------------------------#
	def  analyze_history(self,infileparsings, target_word):
		good_lines = dict()
		#line_locations = list()
		if  target_word not in self.m_Glossary:
			print ("Target word not found in corpus.")
		for lineno, startposition in self.m_Glossary[target_word]:
			if lineno not in good_lines:
				good_lines[lineno] = list()
			good_lines[lineno].append(startposition)
		iteration = 0
		line_number = 0
		while (infileparsings):
			line = infileparsings.readline()
			if len(line) == 0:
				continue
			#print (590, line)
			#print (590, line)
			#breakpoints = line.split()
			#print (592, breakpoints)
			#print()
			#if len(breakpoints) == 0:
			#	continue
			line = line.split()
			#print (597, line)
			if line[0] == "#current_iteration#":
				iteration = line[1]
				print ("New iteration ", iteration)
				line_number = 0
				self.m_Profiles[iteration] = dict()
				continue
			breakpoints  = [int(a) for a in line]
			#print (603, breakpoints)
			#print()
			if (line_number in good_lines):				 
				#print (607, breakpoints)
				for startpoint in good_lines[line_number]:
					multiword = self.analyze(line_number, target_word, startpoint, breakpoints)
					print (609, target_word, multiword)

			line_number += 1


	# ---------------------------------------------------------#
	# returns a string
	def corpus_slice(self, line_number, start_position, length):
		return self.m_Corpus[line_number][start_position:start_position + length]
	# ---------------------------------------------------------#
	def corpus_slice_from_piece_number(self, line_number, breakpoint_list, piece_number):
		start_position = breakpoint_list[piece_number]
		end_position = breakpoint_list[piece_number + 1]
		length = end_position - start_position
		return self.corpus_slice(line_number, start_position, length )

	# ---------------------------------------------------------#
	# not currently used: returns a piece index number 
	def position2true_piece(self, line_number, position):
		pointing_to = 0
		for n in range(self.m_TrueBreakPointList[line_number]):			
			if pointing_to >= position:
				return n
			position += self.m_TrueBreakPointList[line_number][n]	
		return -1		
 	# ---------------------------------------------------------#
 	# Given a position in a string, return the piece number of the breakpoint list that it is in
	def position2chunk_number (self,  breakpoint_list, position):
		pointing_to = 0
		for n in  range(len(breakpoint_list)):
			if breakpoint_list[n] == position:
				#print (648, "position ", position, "found in chunk number ", n)
				return n;
			if breakpoint_list[n] > position:
				return n-1
		return -1	
 	# ---------------------------------------------------------#
	def piece_number2slice(self, line_number, breakpoints, chunk_number):
		#print (652, "chunk number", chunk_number)
		start_position = breakpoints[chunk_number]
		end = breakpoints[chunk_number+1]
		#print (657, "chunk ", self.m_Corpus[line_number][start_position:end])
		return self.m_Corpus[line_number][start_position:end]

 	# ---------------------------------------------------------#
 	# This does not need to be part of the Class.
 	# Returns start and end positions, given a position and a breakpoint list
	def parse_piece2position(self, breakpoint_list, parse_piece_index):
		start_position = 0
		for n in range(len(breakpoint_list)-1):
			if (n == parse_piece_index):
				end_position = start_position + breakpoint_list[n]
				return ((start_position, end_position))		
			start_position += breakpoint_list[n]
		return (-1,-1)
 	# ---------------------------------------------------------#
 	# takes breakpoint list and two breakpoint indexes, and gives a string of letters
	def corpus_slice_sequence(self, line_number, breakpoint_list, first_piece_number, last_piece_number):
		resulting_slice = ""
		#print (655, "corpus slice sequence")
		for n in range(first_piece_number, last_piece_number +1):
			if len(resulting_slice) != 0:
				resulting_slice += " "
			chunk_number = 	self.position2chunk_number( breakpoint_list, n )
			chunk = self.corpus_slice_from_piece_number(line_number, breakpoint_list, n  )
			resulting_slice += chunk
		return resulting_slice	
# ---------------------------------------------------------#
	# takes word, and provides a string
	# which shows how that True Parse is analyzed in the parse
	# provided by "breakpoints".
	def analyze(self, line_number, target_word, startpoint, breakpoints):
		start_chunk_number = self.position2chunk_number(breakpoints, startpoint) 
		endpoint = startpoint + len(target_word) - 1
		end_chunk_number = self.position2chunk_number( breakpoints,endpoint)
		end_chunk = self.piece_number2slice(line_number, breakpoints, end_chunk_number)
		return self.corpus_slice_sequence(line_number, breakpoints, start_chunk_number, end_chunk_number)


		if(False):
				for n in range(len(pieces)):
					if pointing_to == startpoint:
						output = self.corpus_slice(line_number, startpoint,  pieces[n])
						print ("step 1a ", pieces[n])
						break 
					if pointing_to > startpoint:
						output = self.corpus_slice(line_number, startpoint,  pieces[n-1])
						print ("step 1b ", pieces[n]) 
						break;
					if n == len(pieces) - 1:
						output = self.corpus_slice(line_number, startpoint,  pieces[n])
						print ("step 1c ", pieces[n])
						break
					if pointing_to + pieces[n+1] > startpoint:
						output = self.corpus_slice(line_number, startpoint,  pieces[n])
						print ("step 1d ", pieces[n+1]) 
						#pointing_to  += len(pieces[n])
						break;
				pointing_to += pieces[n]
				n += 1		
				print ("Step 2" , output, "start point", startpoint, "n", n, "endpoint ", endpoint)
				while pointing_to < endpoint:
					output += " " + self.corpus_slice(line_number, pointing_to,  pieces[n])
					print ("2 " + output, )
					pointing_to += pieces[n]
		return output
# ---------------------------------------------------------#
#-----------------------------------------#
	def read_parses_from_files_and_analyze_word(target):
		return

#-----------------------------------------#



def PrintList(my_list, outfile):
	print (file=outfile)
	for item in my_list:
		print (item,file=outfile, end = " ") 

#---------------------------------------------------------#

def breakpoints2chunks(breakpoint_list):
	chunks = list()
	for i in range(1, len(breakpoint_list)):
		chunks.append(breakpoint_list[i]-breakpoint_list[i-1])
	return chunks
def chunks2breakpoints(chunk_list):
	breakpoint_list = list()
	breakpoint_list.append(0)
	point = 0
	for i in range(len(chunk_list)):
		point += chunk_list[i]
		breakpoint_list.append(point)
	return breakpoint_list


# This is not a function in the class Lexicon
def analyze_history_2(infile_parsings, target_word):
		good_lines = dict()
		#line_locations = list()
		if  target_word not in self.m_Glossary:
			print ("Target word not found in corpus.")
		for lineno, startposition in self.m_Glossary[target_word]:
			if lineno not in good_lines:
				good_lines[lineno] = list()
			good_lines[lineno].append(startposition)
		iteration = 0
		line_number = 0
		while (infileparsings):
			line = infileparsings.readline()
			if len(line) == 0:
				continue
			#print (590, line)
			#print (590, line)
			#breakpoints = line.split()
			#print (592, breakpoints)
			#print()
			#if len(breakpoints) == 0:
			#	continue
			line = line.split()
			#print (597, line)
			if line[0] == "#current_iteration#":
				iteration = line[1]
				print ("New iteration ", iteration)
				line_number = 0
				self.m_Profiles[iteration] = dict()
				continue
			breakpoints  = [int(a) for a in line]
			#print (603, breakpoints)
			#print()
			if (line_number in good_lines):				 
				#print (607, breakpoints)
				for startpoint in good_lines[line_number]:
					multiword = self.analyze(line_number, target_word, startpoint, breakpoints)
					print (609, target_word, multiword)

			line_number += 1

################################################################################
# The following code develops lexicon from a broken corpus when this file is run
# from the command line. 
#
# The user should provide:
#   - datadirectory -- path the to the corpus file
#
#   - corpusfile -- name of the corpus file
#
#   - shortoutname -- a name used to identify the different outfiles that a run 
#     of this code will generate for this run of the code
#
# The user may also specify:
#   - numberofcycles -- the number of times the model should generate new 
#     word-candidates on this run
#
#   - howmanycandidatesperiteration -- the number of candidates the model should
#     generate during each iteration 
#
# Running this code prints information to a number of outfiles.
#
# Outfiles:
#   <shortoutname>.txt
#       - This is the general outfile. It records:
#           * high level information about this cycle (number of cycles etc.)
#           * the new candidate words chosen in each iteration, when they are 
#             chosen, and how many times they appear
#           * corpus cost, dictionary cost, and description length at each 
#             iteration 
#           * recall and precision in each iteration
#
#   <shortoutname>_processed_corpus.txt
#       - the unbroken corpus, line-by-line, with true breakpoint info
#
#   <shortoutname>_iterated_parsings.txt
#       - where breakpoints were inserted in the best parse of each iteration
#
#   <shortoutname>_final_broken_corpus.txt
#       - the parsed corpus is printed here
#
#   <shortoutname>_lexicon.txt"
#       - each entry in the lexicon and its count in each iteration
#       - entries which were removed from the lexicon and when they were removed
#
#   <shortoutname>_simple_lexicon.txt
#       - each entry in the lexicon
#
#   <shortoutname>_RecallPrecision.tsv
#      - recall and precision in the last iteration
#
#   <shortoutname>_glossary.txt
#       - The true words in the original corpus, and where they appear
# [WF]

 
total_word_count_in_parse 	= 0
g_encoding 					= "utf8"  
numberofcycles 				= 50
howmanycandidatesperiteration = 100
numberoflines 				=  51763
		


datadirectory 			= "../../data/english-browncorpus/"
corpusfile 				= "browncorpus.txt"
shortoutname 			= "wordbreaker_brown_corpus_"+ str(numberofcycles) + "_iters_" + str(howmanycandidatesperiteration) + "_new_per_iteration"

#datadirectory 			= "../../data/russian/"
#corpusfile 			= "russian.txt"
#shortoutname 			= "wordbreaker-russian-" 



#datadirectory 			= "../../data/french/"
#corpusfile 			= "encarta_french_UTF8.txt"
#shortoutname 			= "wordbreaker-encarta-" 

#datadirectory 			= "../../data/spanish/"
#corpusfile 			= "DonQuijoteutf8.txt"
#shortoutname 			= "wordbreaker-donquijote-" 


corpusfilename 			= datadirectory  + corpusfile
outdirectory 			= datadirectory + "wordbreaking/"
outfilename 			= outdirectory + shortoutname+  ".txt" 
outfilename_processed_corpus 	= outdirectory + shortoutname + "_processed_corpus.txt"	
outfilename_parsings			= outdirectory + shortoutname + "_iterated_parsings.txt"
		
outfile_corpus_name		    = outdirectory + shortoutname + "_final_broken_corpus.txt"
outfile_lexicon_name	    = outdirectory + shortoutname + "_lexicon.txt"
outfile_simple_lexicon_name	= outdirectory + shortoutname + "_simple_lexicon.txt"
outfile_RecallPrecision_name= outdirectory + shortoutname + "_RecallPrecision.tsv"
glossary_name				= outdirectory + shortoutname + "_glossary.txt";

if g_encoding == "utf8":
	outfile = codecs.open(outfilename, "w", encoding = 'utf-8')
	outfile_processed_corpus = codecs.open(outfilename_processed_corpus, "w", encoding = 'utf-8')
	outfile_parsings = codecs.open(outfilename_parsings, "w", encoding = 'utf-8')
	outfile_corpus = codecs.open(outfile_corpus_name, "w", encoding = 'utf-8')
	outfile_lexicon = codecs.open(outfile_lexicon_name, "w",encoding = 'utf-8')
	outfile_simple_lexicon = open (outfile_simple_lexicon_name, "w", encoding = 'utf-8')
	outfile_RecallPrecision = codecs.open(outfile_RecallPrecision_name, "w", encoding = 'utf-8')
	outfile_glossary 	= codecs.open(glossary_name, "w", encoding = 'utf-8')		
else:
	outfile = open(outfilename, "w")
	outfile_processed_corpus = open(outfilename_processed_corpus, "w") 	
	outfile_parsings = open(outfilename_iterated_parsings, "w")
	outfile_corpus = open(outfile_corpus_name, "w")
	outfile_lexicon = open(outfile_lexicon_name, "w")
	outfile_simple_lexicon = open (outfile_simple_lexicon_name, "w")
	outfile_RecallPrecision = open(outfile_RecallPrecision_name, "w")
	outfile_glossary 	= codecs.open(glossary_name, "w")
	# Note that "outfile_processed_corpus" is the new output, July 29 2023, to output the entire best parse for each iteration.

print  ("#" + str(corpusfile), file = outfile)
print  ("#" + str(numberofcycles) + " cycles.", file = outfile)
print  ("#" + str(numberoflines) + " lines in the original corpus.", file = outfile)
print  ("#" + str(howmanycandidatesperiteration) + " candidates on each cycle.", file = outfile)

current_iteration = 0	
this_lexicon = Lexicon()
this_lexicon.ReadBrokenCorpus (corpusfilename, numberoflines)
print ( "#" + str(len(this_lexicon.m_TrueDictionary)) + " distinct words in the original corpus.", file=outfile)
this_lexicon.PrintBrokenCorpus(outfile_processed_corpus, outfile_glossary)
print ("finished printing broken corpus",outfilename_processed_corpus)

if not os.path.isfile(outfilename_processed_corpus):
			print ("Warning: ", outfilename_processed_corpus, " does not exist.")
if g_encoding == "utf8":
			infile = codecs.open(outfilename_processed_corpus, encoding = 'utf-8')
else:
			infile = open(outfilename_processed_corpus) 	 
infile_processed_corpus = open(outfilename_processed_corpus)
# do something with it

filename_parsings			= outdirectory + shortoutname + "_iterated_parsings.txt"
if not os.path.isfile(filename_parsings):
			print ("Warning: ",  filename_parsings, " does not exist.")
if g_encoding == "utf8":
			infile = codecs.open(filename_parsings, encoding = 'utf-8')
else:
			infile = open(filename_parsings) 	 
infile_parsings = open(filename_parsings)




if (True):
		#if g_encoding == "utf8":
		#	outfile_2 = codecs.open(outfilename_processed_iterated_parsings, "a", encoding = 'utf-8')
		#else:
		#	outfile_2 = open(outfilename_iterated_parsings, "a") 	

		this_lexicon.ParseCorpus (outfile, outfile_parsings,  current_iteration)
		for current_iteration in range(1, numberofcycles):
			print ("\n Iteration number", current_iteration, "out of ", numberofcycles)
			print ("\n Iteration number", current_iteration, "out of ", numberofcycles, file = outfile)
			this_lexicon.GenerateCandidates(howmanycandidatesperiteration, outfile)
			this_lexicon.ParseCorpus (outfile, outfile_parsings, current_iteration)	 
			this_lexicon.RecallPrecision(current_iteration, outfile,total_word_count_in_parse)
				
		this_lexicon.PrintParsedCorpus(outfile_corpus)
		this_lexicon.PrintLexicon(outfile_lexicon)
		this_lexicon.PrintSimpleLexicon(outfile_simple_lexicon)
		this_lexicon.PrintRecallPrecision(outfile_RecallPrecision) 	 
		outfile.close()
		outfile_processed_corpus.close()
		outfile_corpus.close()
		outfile_lexicon.close()
		outfile_simple_lexicon.close()
		outfile_RecallPrecision.close()
		outfile_glossary.close()


 

