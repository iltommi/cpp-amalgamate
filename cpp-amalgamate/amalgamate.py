import os
import sys
import re
import shutil
from collections import deque

PARSE_FILE = 0
EXTERNAL_FILE = 1
ALREADY_SCANNED = 2

CPP_SRC_FILE_EXT = set([ ".cpp" ,  ".c" ,  ".cxx", ".cc"])
CPP_HEADER_FILE_EXT = set([".hpp" , ".h" , ".hxx" , ".hh" , ".inl"])

INCLUDE_FILE_MATCHER = re.compile(r'#include\s*[<\"]([\w.\\/]*)[>\"]')
UP_DIRECTORY_MATCHER = re.compile(r'(..[\\/])')

def IsCppHeaderFile(ext):
	return  ext in CPP_HEADER_FILE_EXT
	
def IsCppSourceFile(ext):
	return ext in CPP_SRC_FILE_EXT

def IsCppFile(ext):
	return IsCppHeaderFile(ext) or IsCppSourceFile(ext)
	
def AdjustFileExtension(ext):
	if ext[0] != '.':
		ext = '.' + ext
	

class SourceInfo:
	def __init__(self, baseDir , outputDir, outputName):
		self.scannedFiles = set()
		
		self.headerQueue = deque()
		self.sourceQueue = deque()
		
		self.sourceDirs = list()
		self.includeDirs = list()
		
		self.baseDir = baseDir;
		
		self.outputDir = outputDir
		
		self.sourceAmalgamation = None
		self.headerAmalgamation = None
		
		self.outputName = outputName
		self.sourceFileExt = ".cpp"
		self.headerFileExt = ".hpp"
		self.verbose = 1
		
		self.AddSourceDirectory(os.path.join(self.baseDir, "src"))
		self.AddIncludeDirectory(os.path.join(self.baseDir, "include"))
		
	def LogMessage(self, message, level = 1):
		if level >= self.verbose:
			print(message)
		
	def AddSourceDirectory(self, path):
		if not os.path.exists(path): return False
		
		self.LogMessage("Source Directory Added: " + path)
		self.sourceDirs.append(path)
		return True
	
	def AddIncludeDirectory(self, path):
		if not os.path.exists(path): return False
		
		self.LogMessage("Include Directory Added: " + path)
		self.includeDirs.append(path)
		return True
		
	def InitAmalgamationStreams(self):
		headerName = self.outputName + self.headerFileExt
		headerPath = os.path.join(self.outputDir , headerName)
		sourcePath = os.path.join(self.outputDir , self.outputName + self.sourceFileExt)
		
		self.headerAmalgamation = open (headerPath , 'w')
		self.sourceAmalgamation = open (sourcePath , 'w')
		
		self.sourceAmalgamation.write('#include"%s"\n' % (headerName))
		
		print ("creating source Amalgamation:" + sourcePath)
		print ("creating source Amalgamation:" + headerPath)
		
	def CloseAmalgamationStreams(self):
		self.headerAmalgamation.close()
		self.sourceAmalgamation.close()                                                                                                          
		
	def GetOutputStreamForExt(self , ext):
		if IsCppSourceFile(ext):
			return self.sourceAmalgamation
			
		elif IsCppHeaderFile(ext):
			return self.headerAmalgamation
			
		return None
				
	def SetSourceFileExt(ext):
		AdjustFileExtension(ext)
		
		if not IsCppSourceFile(ext):
			print ("Warning: %s is not a recognized c++ source file extension" % (ext))
		
		self.sourceFileExt = ext
		
	def SetHeaderFileExt(ext):
		AdjustFileExtension(ext)
		
		if not IsCppHeaderFile(ext):
			print ("Warning: %s is not a recognized c++ header file extension" % (ext))
		
		self.sourceFileExt = ext
	
	def PrintParseFileMessage(self , message , path  , depth):
		tabs = ''
		for i in range(depth):
			tabs = tabs + '\t'
		
		print ("%s%s: %s" % (tabs , message ,  path))
		

		                                          
	def GetAbsoluteSourcePath(self, pwd, include):
		if os.path.isabs(include):
			return include
		
		#todo: handle "../" in include string -- result = UP_DIRECTORY_MATCHER.findall(include)
		
		for includeDir in self.includeDirs:
			absPath = os.path.join(includeDir , include)
			if os.path.exists(absPath): return absPath
			
		
		for sourceDir in self.sourceDirs:
			absPath = os.path.join(sourceDir , include)
			if os.path.exists(absPath): return absPath
		
		return None
		
	def ShouldParseFile(self , path , ext):
		if (path in self.scannedFiles): return ALREADY_SCANNED
		
		if not IsCppFile(ext) or not os.path.exists(path): 
			return EXTERNAL_FILE
		
		return PARSE_FILE
		
	def ScanSourceFile(self, path , depth):
		dirpath , filename = os.path.split(path)
		ext = os.path.splitext(filename)[1]

		info = self.ShouldParseFile(path, ext)
		if info != PARSE_FILE:
			return info
		                                 
		self.LogMessage("scan file: " + path, 5)     
		self.scannedFiles.add(path)
		
		stream = self.GetOutputStreamForExt(ext)
		
		src= open (path , 'r')
		lines = src.readlines()
		for line in lines:
			result = INCLUDE_FILE_MATCHER.findall(line)
			
			if result:
				includeFile = self.GetAbsoluteSourcePath(dirpath, result[0])
				if includeFile == None: continue
				
				call = self.ScanSourceFile(includeFile , depth + 1)
				
				#only include external files once
				if call == EXTERNAL_FILE:
					self.scannedFiles.add(includeFile)
		
		src.close()
		src = None
		
		self.AddFileToQueue(path, ext)
		
		return info
		
	def ParseSourceDirectoies(self):
	
		for sourceDirectory in 	self.sourceDirs:
			for root, subFolders, files in os.walk(sourceDirectory):
				for filename in files:
					path =  os.path.join(root, filename)
					self.ScanSourceFile(path , 0)
		
	def WriteBeginFileHeader(self, filename, stream):
		stream.write("//Begin File: %s\n\n" % (filename))
	
	def WriteEndFileHeader(self, filename, stream):
		stream.write("\n\n\n")
		stream.write("//End File: " +  filename)
		stream.write("\n\n\n")
		
	def AddFileToQueue(self, filename, ext):
		if IsCppHeaderFile(ext):
			self.LogMessage("enqueue header file: " + filename, 5)     
			self.headerQueue.append(filename)
		elif IsCppSourceFile(ext):
			self.LogMessage("enqueue source file: " + filename, 5) 
			self.sourceQueue.append(filename)
				
	def AmalgamateQueue(self, queue, stream):
		while (len(queue) > 0):
			filename = queue.popleft()
			self.WriteFileToStream(filename, stream)

			
	def WriteFileToStream(self, filename, stream):
		source = open(filename, 'r')
		self.LogMessage("Write File: " + filename, 3) 
		self.WriteBeginFileHeader(filename, stream)
		
		lines = source.readlines()
		for line in lines:
			result = INCLUDE_FILE_MATCHER.findall(line)
			
			if result: continue
			stream.write(line)
		
		self.WriteEndFileHeader(filename, stream)
	
	def WriteAlgamationFiles(self):
		self.InitAmalgamationStreams()
		self.AmalgamateQueue(self.headerQueue, self.headerAmalgamation)
		self.AmalgamateQueue(self.sourceQueue, self.sourceAmalgamation)
		self.CloseAmalgamationStreams()
			
baseDir = sys.argv[1]
outputPath = sys.argv[2]
outputName = sys.argv[3]

print ("base dir: " + baseDir)
print ("output dir: " + outputPath)
print ("output name: " + outputName)

sourceInfo = SourceInfo(baseDir , outputPath, outputName)

sourceInfo.ParseSourceDirectoies()
sourceInfo.WriteAlgamationFiles()
