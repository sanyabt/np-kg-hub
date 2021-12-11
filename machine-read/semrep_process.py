import sys, os
from datetime import datetime, timedelta
import pandas as pd
import time
import subprocess
from nltk import tokenize
import requests

'''
make sure MetaMap, WordSenseDisambiguation Server, and SemRep are running - see notes for start and stop commands
'''

workingDir = os.getcwd()
log_dir = workingDir + '/logs/'
utf_path = '/home/sanya/npdi-workspace/machine_read/replace_utf8.jar'

#np = ['greentea', 'kratom']
np = ['greentea_test']
logging = True

extraction = True

count_dict = {'n_success': 0,
			'n_error': 0,
			'n_statements':0,
			'n_files_processed': 0}

pub_year_to_pmid_map = {}

def read_and_write_file(file, filepath_in, filepath_out):
	filepath = filepath_in+file
	
	fileascii = filepath_out+file.split('_')[0]+'_ascii.txt'
	convert_to_ascii = subprocess.run(["java", "-jar", utf_path, filepath], capture_output=True, text=True)
	if convert_to_ascii:
		result = convert_to_ascii.stdout
		sentences = tokenize.sent_tokenize(result)
		fileo = open(fileascii, 'w', encoding='ascii', errors='backslashreplace')
		for item in sentences:
			if sentences.index(item) % 10 == 0:
				fileo.write('\n\n')
			fileo.write(str(item))
		fileo.write('\n')
		fileo.close()
		count_dict['n_files_processed'] += 1 
		return fileascii
	else:
		return None

def process_with_semrep(infile, outfile):
	try:
		result = subprocess.run(['/usr/local/bin/semrep.v1.8', '-L', '2018', '-Z', '2018AA', infile, outfile])
		return result
	except Exception as e:
		print(e)
		try:
			result = subprocess.run(['/usr/local/bin/semrep.v1.8', '-L', '2018', '-Z', '2018AA', '-Q', '0', infile, outfile])
		except Exception as e:
			print(e)
			return None

def get_publication_year(pmid):
	
	if pmid == '':
		return ''
	if pmid in pub_year_to_pmid_map:
		if pub_year_to_pmid_map[pmid] != '':
			return pub_year_to_pmid_map[pmid]
	time.sleep(5)
	uri = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id="+pmid+"&retmode=json"
	pub_year = ''
	response = requests.get(uri)
	if response.status_code == 429:
		time.sleep(5)
		response = requests.get(uri)
	if response.status_code == 200:
		result = response.json()
		pub_year = result['result'][pmid]['pubdate']
		pub_year_to_pmid_map[pmid] = pub_year
	return pub_year

def semrep_extract(filepath):
	result_dict = {
		'index': [],
		'pmid': [],
		'relation': [],
		'year': [],
		'subject_cui': [],
		'object_cui': [],
		'subject_name': [],
		'object_name': [],
		'subject_type': [],
		'object_type': [],
		'sentence': []
	}
	index = 0
	semrep_files = os.listdir(filepath)
	for file in semrep_files:
		pmid = file.split('.')[0]
		
		sem_relations = {
			'items': [],
			'source_sentence': []
		}
		with open(filepath+file, 'r', errors='ignore') as file_sem:
			lines = file_sem.readlines()
		for item in lines:
			if '|||' in item:
				sem_relations['items'].append(item)
				line_no = lines.index(item)
				sem_relations['source_sentence'].append(lines[line_no-2])
		print(len(sem_relations))
		count_dict['n_statements'] += len(sem_relations)
		for rel in sem_relations['items']:
			result_dict['index'].append(index)
			result_dict['pmid'].append(pmid)
			fields = rel.split('|')
			result_dict['subject_cui'].append(fields[2])
			result_dict['object_cui'].append(fields[9])
			result_dict['subject_name'].append(fields[3])
			result_dict['object_name'].append(fields[10])
			result_dict['relation'].append(fields[8])
			result_dict['subject_type'].append(fields[4])
			result_dict['object_type'].append(fields[11])
			pub_year = get_publication_year(pmid)
			result_dict['year'].append(pub_year)
			relation_index = sem_relations['items'].index(rel)
			result_dict['sentence'].append(sem_relations['source_sentence'][relation_index])
			index += 1

	return result_dict

if __name__ == '__main__':

	for item in np:

		inputDirRaw = workingDir + '/output_files/' + item + '/PDFoutput/'
		inputDir = workingDir + '/output_files/'+item+'/semrepInput/'
		outputDir = workingDir + '/output_files/'+item+'/semrepOutput/'
		
		t0=datetime.now()
		log_file = open(log_dir+item + 'semrep_log'+str(t0)+'.txt', 'a')
		log_file.write('Log for '+ item)
		
		text_files = os.listdir(inputDirRaw)
		for file in text_files:
			if 'processed' in file:
				filename = read_and_write_file(file, inputDirRaw, inputDir)
				if filename is not None:
					semrep_process = process_with_semrep(filename, outputDir+file.split('_')[0]+'.txt')
					if semrep_process is not None:
						log_file.write('File processed: '+file)
						count_dict['n_success'] += 1 

					else:
						log_file.write('\nError in processing: '+file)
						count_dict['n_error'] += 1
				else:
					log_file.write('\nText unavailable: '+file)
					count_dict['n_error'] +=1
		

		if extraction:
			result_dict = semrep_extract(outputDir)

		semrep_result = pd.DataFrame(result_dict)
		semrep_result_unique = semrep_result.drop_duplicates(subset=['subject_cui', 'subject_name', 'subject_type',
					'relation', 'object_cui', 'object_name', 'object_type', 'year', 'sentence'])
		semrep_result_unique.to_csv(workingDir+'/output_files/'+item+'/greentea_test_pmid_all_predicates_semrep.tsv', sep='\t', index=False,
					columns=['index', 'pmid', 'subject_cui', 'subject_name', 'subject_type',
					'relation', 'object_cui', 'object_name', 'object_type', 'year', 'sentence'])

		t1 = datetime.now()
		seconds=timedelta.total_seconds(t1-t0)
		log_file.write('\nTotal time: '+ str(seconds)+' seconds')
		log_file.write('\nN_file_hits: '+str(count_dict['n_files_processed']))
		log_file.write('\nN_semrep_hits: '+str(count_dict['n_success']))
		log_file.write('\nN_errors: '+str(count_dict['n_error']))
		log_file.write('\nN_statements: '+str(count_dict['n_statements']))