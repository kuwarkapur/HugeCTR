import hierarchical_parameter_server as hps
import os
import numpy as np
import tensorflow as tf
import struct

args = dict()

args["gpu_num"] = 1                               # the number of available GPUs
args["iter_num"] = 10                             # the number of training iteration
args["slot_num"] = 3                              # the number of feature fields in this embedding layer
args["embed_vec_size"] = 16                       # the dimension of embedding vectors
args["global_batch_size"] = 16384                 # the globally batchsize for all GPUs
args["max_vocabulary_size"] = 30000
args["vocabulary_range_per_slot"] = [[0,10000],[10000,20000],[20000,30000]]
args["ps_config_file"] = "naive_dnn.json"
args["dense_model_path"] = "naive_dnn_dense.model"
args["embedding_table_path"] = "naive_dnn_sparse.model"
args["saved_path"] = "naive_dnn_tf_saved_model"
args["np_key_type"] = np.int64
args["np_vector_type"] = np.float32
args["tf_key_type"] = tf.int64
args["tf_vector_type"] = tf.float32


os.environ["CUDA_VISIBLE_DEVICES"] = ",".join(map(str, range(args["gpu_num"])))

def generate_random_samples(num_samples, vocabulary_range_per_slot, key_dtype = args["np_key_type"]):
    keys = list()
    for range in vocabulary_range_per_slot:
        keys_per_slot = np.random.randint(low=range[0], high=range[1], size=(num_samples, 1), dtype=key_dtype)
        keys.append(keys_per_slot)
    keys = np.concatenate(np.array(keys), axis = 1)
    labels = np.random.randint(low=0, high=2, size=(num_samples, 1))
    return keys, labels

def tf_dataset(keys, labels, batchsize):
    dataset = tf.data.Dataset.from_tensor_slices((keys, labels))
    dataset = dataset.batch(batchsize, drop_remainder=True)
    return dataset


class TrainModel(tf.keras.models.Model):
    def __init__(self,
                 init_tensors,
                 slot_num,
                 embed_vec_size,
                 **kwargs):
        super(TrainModel, self).__init__(**kwargs)
        
        self.slot_num = slot_num
        self.embed_vec_size = embed_vec_size
        self.init_tensors = init_tensors
        self.params = tf.Variable(initial_value=tf.concat(self.init_tensors, axis=0))
        self.fc_1 = tf.keras.layers.Dense(units=256, activation=None,
                                                 kernel_initializer="ones",
                                                 bias_initializer="zeros",
                                                 name='fc_1')
        self.fc_2 = tf.keras.layers.Dense(units=1, activation=None,
                                                 kernel_initializer="ones",
                                                 bias_initializer="zeros",
                                                 name='fc_2')

    def call(self, inputs):
        embedding_vector = tf.nn.embedding_lookup(params=self.params, ids=inputs)
        embedding_vector = tf.reshape(embedding_vector, shape=[-1, self.slot_num * self.embed_vec_size])
        logit = self.fc_2(self.fc_1(embedding_vector))
        return logit, embedding_vector

    def summary(self):
        inputs = tf.keras.Input(shape=(self.slot_num,), dtype=args["tf_key_type"])
        model = tf.keras.models.Model(inputs=inputs, outputs=self.call(inputs))
        return model.summary()
  

class InferenceModel(tf.keras.models.Model):
    def __init__(self,
                 slot_num,
                 embed_vec_size,
                 dense_model_path,
                 **kwargs):
        super(InferenceModel, self).__init__(**kwargs)
        
        self.slot_num = slot_num
        self.embed_vec_size = embed_vec_size
        self.lookup_layer = hps.LookupLayer(model_name = "naive_dnn", 
                                            table_id = 0,
                                            emb_vec_size = self.embed_vec_size,
                                            emb_vec_dtype = args["tf_vector_type"],
                                            name = "lookup")
        self.dense_model = tf.keras.models.load_model(dense_model_path)

    def call(self, inputs):
        embedding_vector = self.lookup_layer(inputs)
        embedding_vector = tf.reshape(embedding_vector, shape=[-1, self.slot_num * self.embed_vec_size])
        logit = self.dense_model(embedding_vector)
        return logit, embedding_vector

    def summary(self):
        inputs = tf.keras.Input(shape=(self.slot_num,), dtype=args["tf_key_type"])
        model = tf.keras.models.Model(inputs=inputs, outputs=self.call(inputs))
        return model.summary()


def train(args):
    init_tensors = np.ones(shape=[args["max_vocabulary_size"], args["embed_vec_size"]], dtype=args["np_vector_type"])
    
    model = TrainModel(init_tensors, args["slot_num"], args["embed_vec_size"])
    model.summary()
    optimizer = tf.keras.optimizers.Adam(learning_rate=0.1)
    
    loss_fn = tf.keras.losses.BinaryCrossentropy(from_logits=True)
    
    def _train_step(inputs, labels):
        with tf.GradientTape() as tape:
            logit, embedding_vector = model(inputs, training=True)
            loss = loss_fn(labels, logit)
        grads = tape.gradient(loss, model.trainable_variables)
        optimizer.apply_gradients(zip(grads, model.trainable_variables))
        return logit, embedding_vector, loss

    keys, labels = generate_random_samples(args["global_batch_size"]  * args["iter_num"], args["vocabulary_range_per_slot"],  args["np_key_type"])
    dataset = tf_dataset(keys, labels, args["global_batch_size"])
    for i, (id_tensors, labels) in enumerate(dataset):
        _, embedding_vector, loss = _train_step(id_tensors, labels)
        print("-"*20, "Step {}, loss: {}".format(i, loss),  "-"*20)

    return model

def convert_to_sparse_model(embeddings_weights, embedding_table_path, embedding_vec_size):
    os.system("mkdir -p {}".format(embedding_table_path))
    with open("{}/key".format(embedding_table_path), 'wb') as key_file, \
        open("{}/emb_vector".format(embedding_table_path), 'wb') as vec_file:
      for key in range(embeddings_weights.shape[0]):
        vec = embeddings_weights[key]
        key_struct = struct.pack('q', key)
        vec_struct = struct.pack(str(embedding_vec_size) + "f", *vec)
        key_file.write(key_struct)
        vec_file.write(vec_struct)

def create_and_save_inference_graph(args): 
    model = InferenceModel(args["slot_num"], args["embed_vec_size"], args["dense_model_path"])
    model.summary()
    _, _ = model(tf.keras.Input(shape=(args["slot_num"],), dtype=args["tf_key_type"]))
    model.save(args["saved_path"])

def inference_with_saved_model(args):
    hps.Init(global_batch_size = args["global_batch_size"],
             ps_config_file = args["ps_config_file"])
    model = tf.keras.models.load_model(args["saved_path"])
    model.summary()

    @tf.function
    def _infer_step(inputs, labels):
        logit, embedding_vector = model(inputs, training=True)
        return logit, embedding_vector

    embedding_vectors_peek = list()
    id_tensors_peek = list()
    keys, labels = generate_random_samples(args["global_batch_size"]  * args["iter_num"], args["vocabulary_range_per_slot"],  args["np_key_type"])
    dataset = tf_dataset(keys, labels, args["global_batch_size"])
    for i, (id_tensors, labels) in enumerate(dataset):
        print("-"*20, "Step {}".format(i),  "-"*20)
        _, embedding_vector = _infer_step(id_tensors, labels)
        embedding_vectors_peek.append(embedding_vector)
        id_tensors_peek.append(id_tensors)
    return embedding_vectors_peek, id_tensors_peek

if __name__ == "__main__":
    trained_model = train(args)
    weights_list = trained_model.get_weights()
    embedding_weights = weights_list[-1]
    dense_model = tf.keras.models.Model(trained_model.get_layer("fc_1").input, trained_model.get_layer("fc_2").output)
    dense_model.summary()
    dense_model.save(args["dense_model_path"])


    convert_to_sparse_model(embedding_weights, args["embedding_table_path"], args["embed_vec_size"])
    create_and_save_inference_graph(args)


    embedding_vectors_peek, id_tensors_peek = inference_with_saved_model(args)
    print(embedding_vectors_peek[-1])
    print(id_tensors_peek[-1])

    keys = np.array( tf.reshape( tf.concat(id_tensors_peek, axis=0), [-1]) )
    vectors = np.array( tf.reshape( tf.concat(embedding_vectors_peek, axis=0), [-1, args["embed_vec_size"]])  )


    mse = 0
    for i in range(len(keys)):
        ground_truth = embedding_weights[keys[i]]
        diff = vectors[i]-ground_truth
        mse += np.mean(diff*diff)
    if mse > 1e-3:
        raise RuntimeError("HPS TF Plugin has too large error for embedding vector lookup, mse: {}".format(mse))
        sys.exit(1)
    else:
        print("HPS TF Plugin does well for embedding vector lookup, mse: {}".format(mse))