import yaml
import os
from pprint import pprint
from jinja2 import Environment, FileSystemLoader
from jnpr.junos import Device
from jnpr.junos.utils.config import Config
import uname_pass

def load_yaml_file(yaml_to_load):

     loaded_yaml_file = yaml.safe_load(open(yaml_to_load))
     return loaded_yaml_file

def main(evpn_instances):

     #directory variables relative to where this script sits
     dir_evi = 'evi'
     dir_devices = 'devices'
     dir_templates = 'templates'
     # note - below variable is appended as a suffix to a function
     dir_output_configurations = '/built_configurations'
    
     #filename variables
     cisco_evi_j2_template = 'cisco_evi.j2'
     junos_evi_j2_template = 'junos_evi.j2'

     UID = uname_pass.username
     PWD = uname_pass.password

     file_loader = FileSystemLoader("./")
     env = Environment(loader=file_loader, autoescape=True)
     env.trim_blocks = True
     env.lstrip_blocks = True

     # loop through every state
     for state in evpn_instances['state']:
          current_state = state['name']
          print('********** - started the loop through the state {0} - **********'.format(current_state))

          # loop through each EVI for the state
          for evi in state['evpn_instances']:
               # get specific values from the EVI dictionary type, these will be passed into the device level dictionary for the Jinja2 template
               current_evi_id = evi['id']
               print('&&&&&&&&&& - started the loop through the evi {0} - &&&&&&&&&&'.format(current_evi_id))

               current_evi_access_vlan = evi['access_vlan']
               current_evi_evi_vlan =  evi['evi_vlan']
               current_evi_type = evi['evi_type']
               
               # get the filename of the EVI we want to load 
               filename_to_load = '{0}/{1}/{2}-evi_{3}.yaml'.format(dir_evi,current_state, current_state, str(current_evi_id))

               try:
                    # load the EVI YAML file
                    loaded_evi = load_yaml_file(filename_to_load)

                    # loop through each of the edge routers which are participating in the EVI
                    count_evi_members = len(loaded_evi['members']) 
                    evi_device_iterator = 1 

                    print('########## - starting the looping through provider edge routers that make up EVI {0} - ##########'.format(current_evi_id))
                    for edge_router_in_the_evi in loaded_evi['members']:
                         
                         # get the details of the current edge router
                         device_hostname = edge_router_in_the_evi['hostname']
                         print('########## - starting on device: {0} is {1} of {2} routers in this EVI - ##########'.format(device_hostname, evi_device_iterator, count_evi_members))

                         # get the filename of the edge router
                         edge_router_conf_filename = dir_devices + '/provider_edge/' + device_hostname + '.yaml'
 
                        # load this edge routers details from YAML
                         edge_router_details = load_yaml_file(edge_router_conf_filename)

                         device_loopback = edge_router_details['loopback0']
                         # append the values from the previous values to our current dictionary
                         # we'll pass these into our Jinja2 template
                         edge_router_in_the_evi.update({'lo0': device_loopback})
                         edge_router_in_the_evi.update({'id': current_evi_id})
                         edge_router_in_the_evi.update({'access_vlan' : current_evi_access_vlan})
                         edge_router_in_the_evi.update({'evi_vlan': current_evi_evi_vlan})
                         edge_router_in_the_evi.update({'evi_type': current_evi_type})

                         # load up the appropriate template depending on what the vendor of the device is
                         if edge_router_details['vendor'] == 'Juniper':
                              print('########## - detected {0} is a JUNOS device, loading JUNOS EVI template - ##########'.format(device_hostname))
                              template = env.get_template(dir_templates + '/' + junos_evi_j2_template)
                         elif edge_router_details['vendor'] == 'Cisco' :
                              print('##########  - detected {0} is a Cisco device, loading up Cisco EVI template - ##########'.format(device_hostname))
                              template = env.get_template(dir_templates + '/' + cisco_evi_j2_template)
                         else:
                              print('!!!!!!!!!! - this should never occur. YAML data is incorrect - !!!!!!!!!!')
                              continue

                         # enter our YAML table into the Jinja2 template and spit out the instantiated template
                         rendered_output = template.render(edge_router_in_the_evi)

                         # DEBUGGING ONLY - comment this out when not required
                         # print out what has been instantiated from the jinja2 template
                         print('########## - beginning of output to be written -  ##########')
                         print(rendered_output)
                         print('########## - end of output to be written - ##########')
                         
                         # check if directories exist, if they don't, create
                         try:
                              cwd = os.getcwd()
                              evi_output_dir = cwd + '/built_configurations/' + current_state + '/evi_' + str(current_evi_id)
                              if os.path.exists(evi_output_dir) == False:
                                   os.mkdir(evi_output_dir)
                         except OSError as e:
                              print('!!!!!!!!!! - error making directory: ' + str(e) + ' - !!!!!!!!!!')
                      
                         # write out the evpn instance configuration per device and store in the appropriate directory
                         with open(evi_output_dir + '/' + device_hostname, 'w') as f:
                              f.write(rendered_output)

                         #open up a connection to each router and push the write the configuration to it
                         with Device(host=device_loopback, password=PWD, user=UID, normalize=True) as current_device:
                              with Config(current_device, mode='exclusive') as cu:
                                   cu.load(rendered_output,format='set', merge=True)

                                   #perform a show compare between the candidate and active configuration, display the results to the user
                                   diff = cu.diff(rb_id=0)
                                   
                                   #if the diff returned was none, don't do anything and move on to next device
                                   #otherwise perform a commit check
                                   if diff is not None:
                                        print('########## - changes detected, beginning of show compare results - ##########')
                                        print(diff)
                                        print('########## - changes detected, end of show compare results - ##########')
                                        #perform a commit check, if successful commit; otherwise rollback 
                                        if cu.commit_check() == True:
                                              print('########## - commit check returned successful for deploying EVI {0} on the provider edge {1} - ##########'.format(current_evi_id, device_hostname))
          
                                              # commit the configuration
                                              #cu.commit()
                                        else:
                                              print('########## - commit check returned failure for deploying EVI {1} on the provider edge {1} - ##########'.format(current_evi_id, device_hostname))

                                              # rollback the configuration
                                              #cu.rollback
                                   else:
                                        print('########## - no changes to be made - ##########')

                         print('########## - finishing device: {0} is {1} of {2} routers in this EVI - ##########'.format(device_hostname, evi_device_iterator, count_evi_members))
                         evi_device_iterator +=1
               except Exception as e:
                    print ('!!!!!!!!!! - Exception thrown:' + str(e) + ' - !!!!!!!!!!')
                    continue
              
               print('&&&&&&&&&& - finished the loop through the evi {0} - &&&&&&&&&&'.format(current_evi_id))
          print('********** - finished the loop through the state {0} - **********'.format(current_state))

if __name__ == "__main__":

     devices = load_yaml_file('evi/all-evi.yaml')
     main(devices)
