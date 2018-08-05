import pickle,os,torch
import numpy as np
import json
import prepare_transfer_learning as ptl
import data_loader as dl


#Should be shifted to some other locations
def load_relation(COMMON_DATA_DIR):
    """
        Function used once to load the relations dictionary
        (which keeps the log of IDified relations, their uri and other things.)

    :param relation_file: str
    :return: dict
    """
    relations = pickle.load(open(os.path.join(COMMON_DATA_DIR, 'relations.pickle')))
    inverse_relations = {}
    for key in relations:
        value = relations[key]
        new_key = value[0]
        value[0] = key
        inverse_relations[new_key] = value

    return inverse_relations


#Loads word list from given COMMON_DATA_DIR. To be used by FlatEncoder.
def load_word_list(COMMON_DATA_DIR):
    word_list = pickle.load(open(COMMON_DATA_DIR + '/glove.300d.words'))
    word_to_id = {}
    for index, word in enumerate(word_list):
        word_to_id[word] = index
    return word_to_id

def save_location(problem, model_name, dataset):
    '''
            Location - data/models/problem/model_name/dataset/0X
            problem - core_chain
                    -intent
                    -rdf
                    -type_existence
            model_name - cnn_dense_dense ; pointwise_cnn_dense_dense ....

            dataset -
            return a dir data/models/problem/model_name/dataset/0X
    '''
    # Check if the path exists or not. If not create one.
    assert (problem in ['core_chain', 'intent', 'rdf_class', 'rdf_type'])
    assert (dataset in ['qald', 'lcquad', 'transfer-a', 'transfer-b', 'transfer-c'])

    path = 'data/models/' + str(problem) + '/' + str(model_name) + '/' + str(dataset)
    if not os.path.exists(path):
        os.makedirs(path)
    dir_name = [int(name) for name in os.listdir(path + '/')]
    if not dir_name:
        new_path_dir = path + '/' + str(0)
        os.mkdir(new_path_dir)
    else:
        dir_name = max(dir_name)
        new_model = dir_name + 1
        new_path_dir = path + '/' + str(new_model)
        os.mkdir(new_path_dir)
    return new_path_dir


# Function to save the model
def save_model(loc, modeler, model_name='model.torch', epochs=0, optimizer=None, accuracy=0,aux_save_information={}):
    """
        Input:
            loc: str of the folder where the models are to be saved - data/models/core_chain/cnn_dense_dense/lcquad/5'
            models: dict of 'model_name': model_object
            epochs, optimizers are int, torch.optims (discarded right now).
    """

    state = {
        'epoch': epochs,
        'optimizer': optimizer.state_dict(),
        # 'state_dict': model.state_dict(),
        'accuracy': accuracy
    }
    for tup in modeler.prepare_save():
        state[tup[0]] = tup[1].state_dict()
    aux_save = loc + '/model_info.pickle'
    loc = loc + '/' + model_name
    print("model with accuracy ", accuracy, "stored at", loc)
    torch.save(state, loc)

    _aux_save_information = aux_save_information.copy()
    try:
        _aux_save_information['parameter_dict'].pop('vectors')
    except KeyError:
        print("in model save, no vectors were found.")
        pass
    pickle.dump(_aux_save_information,open(aux_save, 'w+'))


def validation_accuracy(valid_questions, valid_pos_paths, valid_neg_paths, modeler, device):
    precision = []
    with torch.no_grad():
        for i in range(len(valid_questions)):
            question = np.repeat(valid_questions[i].reshape(1, -1), len(valid_neg_paths[i]) + 1,
                                 axis=0)  # +1 for positive path
            paths = np.vstack((valid_pos_paths[i].reshape(1, -1), valid_neg_paths[i]))


            question = torch.tensor(question, dtype=torch.long, device=device)
            paths = torch.tensor(paths, dtype=torch.long, device=device)
            score = modeler.predict(question, paths, device)
            arg_max = torch.argmax(score)
            if arg_max.item() == 0:  # 0 is the positive path index
                precision.append(1)
            else:
                precision.append(0)
    return sum(precision) * 1.0 / len(precision)


def validation_accuracy_alter(valid_questions, valid_pos_paths, valid_neg_paths, modeler, device, qa):
    precision = []

    print(valid_pos_paths.shape)
    print(valid_neg_paths.shape)
    print(valid_questions.shape)


    for i in range(len(valid_questions)):

        question = valid_questions[i]
        paths = np.vstack((valid_pos_paths[i].reshape(1, -1), valid_neg_paths[i]))

        score = qa._predict_corechain(question, paths)
        arg_max = np.argmax(score)
        if arg_max.item() == 0:  # 0 is the positive path index
            precision.append(1)
        else:
            precision.append(0)

    return sum(precision) * 1.0 / len(precision)


def id_to_word(path, gloveid_to_word, embeddingid_to_gloveid, remove_pad = True):
    '''


    :param path: embedding id arrray list
    :param gloveid_to_word:
    :param embeddingid_to_gloveid:
    :param remove_pad:
    :return:
    '''
    sent = []
    for q in path:
        try:
            w = gloveid_to_word[embeddingid_to_gloveid[q]]
            if w != 'PAD' and remove_pad:
                sent.append(w)
        except:
            sent.append('<unk>')
    return " ".join(sent)



def load_embeddingid_gloveid():
    '''
        Loads required dictionary files for id_to_word functionality
    '''
    gloveid_to_embeddingid = pickle.load(open('data/data/common/vocab.pickle'))
    # reverse vocab it
    embeddingid_to_gloveid = {}
    for keys in gloveid_to_embeddingid:
        embeddingid_to_gloveid[gloveid_to_embeddingid[keys]] = keys

    word_to_gloveid = pickle.load(open('./resources/glove_vocab.pickle'))
    gloveid_to_word = {}
    for keys in word_to_gloveid:
        gloveid_to_word[word_to_gloveid[keys]] = keys
    return gloveid_to_embeddingid , embeddingid_to_gloveid, word_to_gloveid, gloveid_to_word

def to_bool(value):
    if str(value) == 'true' or str(value) == 'True':
        return True
    else:
        return False

def load_data(_dataset, _train_over_validation, _parameter_dict, _relations, _pointwise,_device):


    TEMP = data_loading_parameters(_dataset, _parameter_dict)

    _dataset_specific_data_dir,_model_specific_data_dir,_file,\
               _max_sequence_length,_neg_paths_per_epoch_train,_neg_paths_per_epoch_validation,_training_split,_validation_split,_index= TEMP

    _a = dl.load_data(_dataset, _dataset_specific_data_dir, _model_specific_data_dir, _file, _max_sequence_length,
                      _neg_paths_per_epoch_train,
                      _neg_paths_per_epoch_validation, _relations,
                      _index, _training_split, _validation_split, _model='core_chain_pairwise', _pairwise=not _pointwise, _debug=True, _rdf=False)



    if _dataset == 'lcquad':
        train_questions, train_pos_paths, train_neg_paths, dummy_y_train, valid_questions, valid_pos_paths, valid_neg_paths, dummy_y_valid, test_questions, test_pos_paths, test_neg_paths,vectors = _a
    else:
        print("warning: Test accuracy would not be calculated as the data has not been prepared.")
        train_questions, train_pos_paths, train_neg_paths, dummy_y_train, valid_questions, valid_pos_paths, valid_neg_paths, dummy_y_valid, vectors = _a
        test_questions,test_neg_paths,test_pos_paths = None,None,None


    data = {}
    if _train_over_validation:
        data['train_questions'] = np.vstack((train_questions, valid_questions))
        data['train_pos_paths'] = np.vstack((train_pos_paths, valid_pos_paths))
        data['train_neg_paths'] = np.vstack((train_neg_paths,valid_neg_paths))
    else:
        data['train_questions'] = train_questions
        data['train_pos_paths'] = train_pos_paths
        data['train_neg_paths'] = train_neg_paths

    data['valid_questions'] = valid_questions
    data['valid_pos_paths'] = valid_pos_paths
    data['valid_neg_paths'] = valid_neg_paths
    data['test_pos_paths'] = test_pos_paths
    data['test_neg_paths'] = test_neg_paths
    data['test_questions'] = test_questions
    data['vectors'] = vectors
    data['dummy_y'] = torch.ones(_parameter_dict['batch_size'], device=_device)

    return data
def data_loading_parameters(dataset,parameter_dict,runtime=False):

    if dataset == 'lcquad':
        _dataset_specific_data_dir = 'data/data/lcquad/'
        _model_specific_data_dir = 'data/data/core_chain_pairwise/lcquad/'
        _file = 'id_big_data.json'
        _max_sequence_length = parameter_dict['max_length']
        _neg_paths_per_epoch_train = parameter_dict['_neg_paths_per_epoch_train']
        _neg_paths_per_epoch_validation = parameter_dict['_neg_paths_per_epoch_validation']
        _training_split = .7
        _validation_split = .8
        _index = None

    elif dataset == 'qald':
        _dataset_specific_data_dir = 'data/data/qald/'
        _model_specific_data_dir = 'data/data/core_chain_pairwise/qald/'
        if not runtime:
            _file = 'combined_qald.json'
            id_train = json.load(
                open(os.path.join(_dataset_specific_data_dir % {'dataset': dataset}, "qald_id_big_data_train.json")))
            json.dump(id_train, open(os.path.join(_dataset_specific_data_dir % {'dataset': dataset}, _file), 'w+'))
        else:
            _file = 'qald_id_big_data_test.json'



        _max_sequence_length = parameter_dict['max_length']
        _neg_paths_per_epoch_train = parameter_dict['_neg_paths_per_epoch_train']
        _neg_paths_per_epoch_validation = parameter_dict['_neg_paths_per_epoch_validation']
        _training_split = .7
        _validation_split = .8
        if not runtime:
            _index = int(7.0 * (len(id_train)) / 8.0) - 1
        else:
            _index = -1


    elif dataset == 'transfer-a':
        _data_dir = 'data/data/'
        _dataset_specific_data_dir = 'data/data/transfer-a/'
        _model_specific_data_dir = 'data/data/core_chain_pairwise/transfer-a/'
        _max_sequence_length = parameter_dict['max_length']
        _neg_paths_per_epoch_train = parameter_dict['_neg_paths_per_epoch_train']
        _neg_paths_per_epoch_validation = parameter_dict['_neg_paths_per_epoch_validation']
        _training_split = .7
        _validation_split = .8
        _file, _index = ptl.transfer_a()

    elif dataset == 'transfer-b':
        _data_dir = 'data/data/'
        _dataset_specific_data_dir = 'data/data/transfer-b/'
        _model_specific_data_dir = 'data/data/core_chain_pairwise/transfer-b/'
        _max_sequence_length = parameter_dict['max_length']
        _neg_paths_per_epoch_train = parameter_dict['_neg_paths_per_epoch_train']
        _neg_paths_per_epoch_validation = parameter_dict['_neg_paths_per_epoch_validation']
        _training_split = .7
        _validation_split = .8
        _file, _index = ptl.transfer_b()

    elif dataset == 'transfer-c':
        _data_dir = 'data/data/'
        _dataset_specific_data_dir = 'data/data/transfer-c/'
        _model_specific_data_dir = 'data/data/core_chain_pairwise/transfer-c/'
        _max_sequence_length = parameter_dict['max_length']
        _neg_paths_per_epoch_train = parameter_dict['_neg_paths_per_epoch_train']
        _neg_paths_per_epoch_validation = parameter_dict['_neg_paths_per_epoch_validation']
        _training_split = .7
        _validation_split = .8
        _file, _index = ptl.transfer_c()

    elif dataset == 'transfer-proper-qald':
        print("the functionality is still not supported. Kill few kittens to get it to work or give me an ice cream")

    return _dataset_specific_data_dir,_model_specific_data_dir,_file,\
           _max_sequence_length,_neg_paths_per_epoch_train,_neg_paths_per_epoch_validation,_training_split,_validation_split,_index