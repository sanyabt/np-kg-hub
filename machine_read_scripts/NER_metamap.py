from pymetamap import MetaMap
import pickle
import os
import indra
import re
from indra.statements import stmts_from_json_file

#create instance for metamap API, path from local file
workingDir = os.getcwd()
dir_out = workingDir + '/output_files/'
file_reach = dir_out + 'kratom/0_58_reach_output_assembly.json'
dir_log = workingDir + '/logs/'
mm = MetaMap.get_instance('/media/extension-1/UMLS/MetaMap/public_mm/bin/metamap')

with open(dir_out+'umls_dict.pickle', 'rb') as file_p:
	umls_dict = pickle.load(file_p)

#make more sophisticated> currently takes the first MetaMap concept as highest score (same scores ignored)
def extract_concepts_umls(entity, umls_count):
	#re.sub(r”\(|\)“, “”, text)
	entity = re.sub(r'\(|\)', '', entity)
	entity = re.sub(r'[^\x00-\x7F]+','', entity)
	text = [entity]
	#take the concept with highest score
	concepts,error = mm.extract_concepts(text)
	if concepts:
		concept = concepts[0]
		try:
			umls_dict[entity] = {
				'cui': concept.cui,
				'umls_term': concept.preferred_name,
				'sem_type': concept.semtypes.strip('][').split(','),
				'score': float(concept.score)
			}
			umls_count += 1
		except AttributeError:
			pass
	return umls_count
			
if __name__ == '__main__':
	umls_count = 0
	reach_concepts = []
	stmts = stmts_from_json_file(file_reach)
	#for item in stmts:
	#	reach_concepts.extend(item.agent_list())

	for item in stmts:
		agents_list = item.agent_list()
		for agent in agents_list:
			if agent:
				if agent.db_refs:
					if 'TEXT' in agent.db_refs:
						reach_concepts.append(agent.db_refs['TEXT'])
					else:
						reach_concepts.extend(item.agent_list())
				else:
					reach_concepts.extend(item.agent_list())
			else:
				reach_concepts.extend(item.agent_list())
	concepts = set(reach_concepts)
	#call function to extract concepts
	concepts_list = list(concepts)
	print(len(concepts_list))
	index = 0
	for concept in concepts_list:
		umls_count = extract_concepts_umls(str(concept), umls_count)
		index += 1
		if index%1000 == 0:
			print(index)
	total_count = len(concepts_list)

	#save dictionaries to pickle files
	with open(dir_out+'umls_dict_20211004.pickle', 'wb') as file_o:
		pickle.dump(umls_dict, file_o)
	with open(dir_log+'NER_log.txt', 'w') as file_log:
		file_log.write('Total concepts = '+str(total_count))
		file_log.write('\nUMLS mapped concepts = '+str(umls_count))


