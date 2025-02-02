""" This module generates notes for a midi file using the
    trained neural network """
import pickle
import numpy
import argparse
from tqdm import tqdm
from copy import copy
from random import randint,sample
from music21 import instrument, note, stream, chord, meter
from random_word import RandomWords
from keras.models import Sequential
from keras.layers import Dense
from keras.layers import Dropout
from keras.layers import LSTM
from keras.layers import BatchNormalization as BatchNorm
from keras.layers import Activation

OPTIMIZER = 'adagrad'
LOSS = 'categorical_crossentropy'
CELLS = 256

parser = argparse.ArgumentParser()
parser.add_argument('-w', '--weights', type=str, default='model.hdf5', help='The weights')
parser.add_argument('-n', '--number', type=int, default=1, help='Number of outputs')
parser.add_argument('-c', '--cells', type=int, default=CELLS, help='number of lstm cells in each layer')
parser.add_argument('-o', '--optimizer', type=int, default=1, help='active stream optimization')
args = parser.parse_args()

def generate(n):
    """ Generate a piano midi file """
    #load the notes used to train the model
    with open('data/notes', 'rb') as filepath:
        notes = pickle.load(filepath)

    # Get all pitch names
    pitchnames = sorted(set(item for item in notes))
    # Get all pitch names
    n_vocab = len(set(notes))

    network_input, normalized_input = prepare_sequences(notes, pitchnames, n_vocab)
    model = create_network(normalized_input, n_vocab)
    prediction_output = generate_notes(model, network_input, pitchnames, n_vocab)
    create_midi(prediction_output,n)

def prepare_sequences(notes, pitchnames, n_vocab):
    """ Prepare the sequences used by the Neural Network """
    # map between notes and integers and back
    note_to_int = dict((note, number) for number, note in enumerate(pitchnames))

    sequence_length = 64
    network_input = []
    output = []
    for i in range(0, len(notes) - sequence_length, 1):
        sequence_in = notes[i:i + sequence_length]
        sequence_out = notes[i + sequence_length]
        network_input.append([note_to_int[char] for char in sequence_in])
        output.append(note_to_int[sequence_out])

    n_patterns = len(network_input)

    # reshape the input into a format compatible with LSTM layers
    normalized_input = numpy.reshape(network_input, (n_patterns, sequence_length, 1))
    # normalize input
    normalized_input = normalized_input / float(n_vocab)

    return (network_input, normalized_input)

def create_network(network_input, n_vocab):
    """ create the structure of the neural network """
    model = Sequential()
    model.add(LSTM(
        args.cells,
        input_shape=(network_input.shape[1], network_input.shape[2]),
        recurrent_dropout=0.3,
        return_sequences=True
    ))
    model.add(LSTM(args.cells, return_sequences=True, recurrent_dropout=0.2,))
    model.add(LSTM(args.cells, return_sequences=True, recurrent_dropout=0.1,))
    model.add(LSTM(args.cells))
    model.add(BatchNorm())
    model.add(Dropout(0.3))
    model.add(Dense(256))
    model.add(Activation('tanh'))
    model.add(BatchNorm())
    model.add(Dropout(0.3))
    model.add(Dense(n_vocab))
    model.add(Activation('softmax'))
    model.compile(loss=LOSS, optimizer=OPTIMIZER)

    # Load the weights to each node
    model.load_weights(args.weights)

    return model

def generate_notes(model, network_input, pitchnames, n_vocab):
    """ Generate notes from the neural network based on a sequence of notes """
    # pick a random sequence from the input as a starting point for the prediction
    start = numpy.random.randint(0, len(network_input)-1)

    int_to_note = dict((number, note) for number, note in enumerate(pitchnames))

    pattern = network_input[start]
    prediction_output = []

    # generate 500 notes
    for note_index in range(500):
        prediction_input = numpy.reshape(pattern, (1, len(pattern), 1))
        prediction_input = prediction_input / float(n_vocab)

        prediction = model.predict(prediction_input, verbose=0)

        index = numpy.argmax(prediction)
        result = int_to_note[index]
        prediction_output.append(result)

        pattern.append(index)
        pattern = pattern[1:len(pattern)]

    return prediction_output

def set_duration(p, d, o):
    n = p
    try:
        # float representation
        n.duration.quarterLength = float(d)
    except:
        # quarter representation
        if ('/' in d):
            q = d.split('/')
            n.duration.quarterLength = int(q[0]) / int(q[-1])
        else: # string representation
            n.duration = duration.Duration(d)
    n.offset=o
    return n

def get_random_instrument():
    all_instruments = instrument.Instrument.__subclasses__()
    return all_instruments[randint(0, len(all_instruments)-1)]()

def create_midi(prediction_output,n):
    """ convert the output from the prediction to notes and create a midi file
        from the notes """
    offset = 0
    output_notes = []
    instruments = {}

    # create note and chord objects based on the values generated by the model
    for pattern in prediction_output:
        parts = pattern.split()
        _instrument, _notes, _duration, _offset = (parts[0], parts[1:-2], parts[-2], parts[-1])

        if (_instrument not in instruments.keys()):
            instruments[_instrument] = []

        _chord, _note = None, None
        # set duration of chords and notes
        if (isinstance(_notes, list) and len(_notes) > 1):
            _chord = chord.Chord(_notes)
            _chord = set_duration(_chord,_duration,_offset)
            instruments[_instrument].append(_chord)
        elif (isinstance(_notes, list) and len(_notes) == 1):
            _note = note.Note(_notes[0])
            _note = set_duration(_note,_duration,_offset)
            instruments[_instrument].append(_note)

    midi_stream = stream.Score()
    for instrument_key in instruments.keys():
        current_instrument = None
        try:
            current_instrument = instrument.instrumentFromMidiProgram(int(instrument_key))
        except:
            print('%s: WARNING: invalid instrument!' % instrument_key)
            current_instrument = get_random_instrument()
            print('%s: INFO: selected random!' % current_instrument.instrumentName)
        current_part = stream.Part() # only one part is supported now
        current_timesignature = meter.TimeSignature('3/4')

        current_part.append(current_timesignature)
        current_part.append(current_instrument)

        measure_count=0
        for pitch in instruments[instrument_key]:
            current_part.append(pitch)

        midi_stream.append(current_part)
        if args.optimizer:
            for p in midi_stream.parts:
                p.makeMeasures(inPlace=True)

    if args.optimizer:
        midi_stream.makeNotation(inPlace=True)

    names = [s.lower() for s in sample(RandomWords().get_random_words(),2)]
    midi_stream.write('midi', fp='%s_%s.mid' % tuple(names))

if __name__ == '__main__':
    for n in tqdm(range(0, args.number)):
        generate(n)
