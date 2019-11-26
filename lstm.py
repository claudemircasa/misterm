""" This module prepares midi file data and feeds it to the neural
    network for training """
import glob
import pickle
import numpy
from tqdm import tqdm
from random import randint
from music21 import converter, instrument, note, chord, stream
from keras.models import Sequential
from keras.layers import Dense
from keras.layers import Dropout
from keras.layers import LSTM
from keras.layers import Activation
from keras.layers import BatchNormalization as BatchNorm
from keras.utils import np_utils
from keras.callbacks import ModelCheckpoint

def train_network():
    """ Train a Neural Network to generate music """
    notes = get_notes()

    # get amount of pitch names
    n_vocab = len(set(notes))

    network_input, network_output = prepare_sequences(notes, n_vocab)

    model = create_network(network_input, n_vocab)

    train(model, network_input, network_output)

def get_notes():
    """ Get all the notes and chords from the midi files in the ./midi_songs directory """
    notes = []

    files = tqdm(glob.glob("dataset/*.mid"))
    for file in files:
        midi = converter.parse(file)

        files.set_description("Parsing %s" % file)

        notes_to_parse = None

        try: # file has instrument parts
            s2 = instrument.partitionByInstrument(midi)
            # notes_to_parse = s2.parts[0]
            notes_to_parse = s2.parts
        except: # file has notes in a flat structure
            notes_to_parse = midi.flat.notes

        for _instrument in notes_to_parse:
            # the first element is the instrument midi representation
            ri = instrument.Instrument.__subclasses__()
            # iid = ri[randint(0, len(ri)-1)]().instrumentName.replace(' ', '_')
            iid = ri[randint(0, len(ri)-1)]().midiProgram

            # format is: [<instrument>, <note>, <duration>]
            if (isinstance(_instrument, note.Note)):
                notes.append('%s %s %s %s' % (iid, str(_instrument.pitch), _instrument.duration.quarterLength, _instrument.offset))
            elif (isinstance(_instrument, stream.Part)):
                if (not _instrument.getInstrument(returnDefault=False).instrumentName == None):
                    iid = _instrument.getInstrument(returnDefault=False).midiProgram
                for element in _instrument:
                    if isinstance(element, note.Note):
                        notes.append('%s %s %s %s' % (iid, str(element.pitch), element.duration.quarterLength, element.offset))
                    elif isinstance(element, chord.Chord):
                        notes.append('%s %s %s %s' % (iid, ' '.join(str(p) for p in element.pitches), element.duration.quarterLength, element.offset))

    with open('data/notes', 'wb') as filepath:
        pickle.dump(notes, filepath)

    return notes

def prepare_sequences(notes, n_vocab):
    """ Prepare the sequences used by the Neural Network """
    sequence_length = 100

    # get all pitch names
    pitchnames = sorted(set(item for item in notes))

     # create a dictionary to map pitches to integers
    note_to_int = dict((note, number) for number, note in enumerate(pitchnames))

    network_input = []
    network_output = []

    # create input sequences and the corresponding outputs
    for i in range(0, len(notes) - sequence_length, 1):
        sequence_in = notes[i:i + sequence_length]
        sequence_out = notes[i + sequence_length]
        network_input.append([note_to_int[char] for char in sequence_in])
        network_output.append(note_to_int[sequence_out])

    n_patterns = len(network_input)

    # reshape the input into a format compatible with LSTM layers
    network_input = numpy.reshape(network_input, (n_patterns, sequence_length, 1))
    # normalize input
    network_input = network_input / float(n_vocab)

    network_output = np_utils.to_categorical(network_output)

    return (network_input, network_output)

def create_network(network_input, n_vocab):
    """ create the structure of the neural network """
    model = Sequential()
    model.add(LSTM(
        512,
        input_shape=(network_input.shape[1], network_input.shape[2]),
        recurrent_dropout=0.3,
        return_sequences=True
    ))
    model.add(LSTM(512, return_sequences=True, recurrent_dropout=0.3,))
    model.add(LSTM(512))
    model.add(BatchNorm())
    model.add(Dropout(0.3))
    model.add(Dense(256))
    model.add(Activation('relu'))
    model.add(BatchNorm())
    model.add(Dropout(0.3))
    model.add(Dense(n_vocab))
    model.add(Activation('softmax'))
    model.compile(loss='categorical_crossentropy', optimizer='rmsprop')

    return model

def train(model, network_input, network_output):
    """ train the neural network """
    filepath = "weights-improvement-{epoch:02d}-{loss:.4f}-bigger.hdf5"
    checkpoint = ModelCheckpoint(
        filepath,
        monitor='loss',
        verbose=0,
        save_best_only=True,
        mode='min'
    )
    callbacks_list = [checkpoint]

    model.fit(network_input, network_output, epochs=2000, batch_size=128, callbacks=callbacks_list)

if __name__ == '__main__':
    train_network()
