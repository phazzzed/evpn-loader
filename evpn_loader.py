import yaml
import os
from pprint import pprint
from jinja2 import Environment, FileSystemLoader

def load_yaml_file(yaml_to_load):

     loaded_yaml_file = yaml.safe_load(open(yaml_to_load))
     return loaded_yaml_file


def main(evpn_instances):
     
     file_loader = FileSystemLoader("./")
     env = Environment(loader=file_loader, autoescape=True)
     env.trim_blocks = True
     env.lstrip_blocks = True

     for each_state in evpn_instances['state']:
          #print('state name: ' + each_state['name'])
          current_state = each_state['name']

          for each_evi in each_state['evpn_instances']:
               #print('evi id: ' + str(each_evi['id']))
               current_id = each_evi['id']
               
               #filename_to_load = 'evi/' + str(each_state['name']) + '/' + str(each_state['name']) + 'evi_' + str(each_evi['id']) + '.yaml'
               filename_to_load = 'evi/{0}/{1}-evi_{2}.yaml'.format(current_state, current_state, str(current_id))
               #print('opening evi file: ' + filename_to_load)

               try:
                    loaded_evi = load_yaml_file(filename_to_load)
                    template = env.get_template('templates/junos_evi.j2') 
                    for each_edge_router in loaded_evi['members']:
                         output = template.render(each_edge_router)
                         
                         try:
                              cwd = os.getcwd()
                              evi_output_dir = cwd + '/built_configurations/' + current_state + '/evi_' + str(current_id)
                              if os.path.exists(evi_output_dir) == False:
                                   os.mkdir(evi_output_dir)
                         except OSError as e:
                              print('error making directory: ' + str(e))
                         #print(output) 
                         with open(evi_output_dir + '/' + each_edge_router['hostname'], 'w') as f:
                              f.write(output) 
                         
               except Exception as e:
                    print (e)
                    continue
              

if __name__ == "__main__":

     devices = load_yaml_file('evi/all-evi.yaml')
     main(devices)
