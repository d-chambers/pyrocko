import time
import logging

import numpy as num

from pyrocko.guts import StringChoice, StringPattern, UnicodePattern, String,\
    Unicode, Int, Float, List, Object, Timestamp, ValidationError
from pyrocko.guts import load_xml  # noqa

from pyrocko import trace, model

guts_prefix = 'pf'

logger = logging.getLogger('pyrocko.fdsn.station')

conversion = {
    ('M', 'M'): None,
    ('M/S', 'M'): trace.IntegrationResponse(1),
    ('M/S**2', 'M'): trace.IntegrationResponse(2),
    ('M', 'M/S'): trace.DifferentiationResponse(1),
    ('M/S', 'M/S'): None,
    ('M/S**2', 'M/S'): trace.IntegrationResponse(1),
    ('M', 'M/S**2'): trace.DifferentiationResponse(2),
    ('M/S', 'M/S**2'): trace.DifferentiationResponse(1),
    ('M/S**2', 'M/S**2'): None}


class NoResponseInformation(Exception):
    pass


class MultipleResponseInformation(Exception):
    pass


def wrap(s, width=80, indent=4):
    words = s.split()
    lines = []
    t = []
    n = 0
    for w in words:
        if n + len(w) >= width:
            lines.append(' '.join(t))
            n = indent
            t = [' '*(indent-1)]

        t.append(w)
        n += len(w) + 1

    lines.append(' '.join(t))
    return '\n'.join(lines)


def same(x, eps=0.0):
    if any(type(x[0]) != type(r) for r in x):
        return False

    if isinstance(x[0], float):
        return all(abs(r-x[0]) <= eps for r in x)
    else:
        return all(r == x[0] for r in x)


class Nominal(StringChoice):
    choices = [
        'NOMINAL',
        'CALCULATED']


class Email(UnicodePattern):
    pattern = u'[\\w\\.\\-_]+@[\\w\\.\\-_]+'


class RestrictedStatus(StringChoice):
    choices = [
        'open',
        'closed',
        'partial']


class Type(StringChoice):
    choices = [
        'TRIGGERED',
        'CONTINUOUS',
        'HEALTH',
        'GEOPHYSICAL',
        'WEATHER',
        'FLAG',
        'SYNTHESIZED',
        'INPUT',
        'EXPERIMENTAL',
        'MAINTENANCE',
        'BEAM']

    class __T(StringChoice.T):
        def validate_extra(self, val):
            if val not in self.choices:
                logger.warn(
                    'channel type: "%s" is not a valid choice out of %s' %
                    (val, repr(self.choices)))


class PzTransferFunction(StringChoice):
    choices = [
        'LAPLACE (RADIANS/SECOND)',
        'LAPLACE (HERTZ)',
        'DIGITAL (Z-TRANSFORM)']


class Symmetry(StringChoice):
    choices = [
        'NONE',
        'EVEN',
        'ODD']


class CfTransferFunction(StringChoice):

    class __T(StringChoice.T):
        def validate(self, val, regularize=False, depth=-1):
            if regularize:
                try:
                    val = str(val)
                except ValueError:
                    raise ValidationError(
                        '%s: cannot convert to string %s' % (self.xname,
                                                             repr(val)))

                val = self.dummy_cls.replacements.get(val, val)

            self.validate_extra(val)
            return val

    choices = [
        'ANALOG (RADIANS/SECOND)',
        'ANALOG (HERTZ)',
        'DIGITAL']

    replacements = {
        'ANALOG (RAD/SEC)': 'ANALOG (RADIANS/SECOND)',
    }


class Approximation(StringChoice):
    choices = [
        'MACLAURIN']


class PhoneNumber(StringPattern):
    pattern = '[0-9]+-[0-9]+'


class Site(Object):
    '''Description of a site location using name and optional
    geopolitical boundaries (country, city, etc.).'''

    name = Unicode.T(xmltagname='Name')
    description = Unicode.T(optional=True, xmltagname='Description')
    town = Unicode.T(optional=True, xmltagname='Town')
    county = Unicode.T(optional=True, xmltagname='County')
    region = Unicode.T(optional=True, xmltagname='Region')
    country = Unicode.T(optional=True, xmltagname='Country')


class ExternalReference(Object):
    '''This type contains a URI and description for external data that
    users may want to reference in StationXML.'''

    uri = String.T(xmltagname='URI')
    description = Unicode.T(xmltagname='Description')


class Units(Object):
    '''A type to document units. Corresponds to SEED blockette 34.'''

    def __init__(self, name=None, **kwargs):
        Object.__init__(self, name=name, **kwargs)

    name = String.T(xmltagname='Name')
    description = Unicode.T(optional=True, xmltagname='Description')


class Counter(Int):
    pass


class SampleRateRatio(Object):
    '''Sample rate expressed as number of samples in a number of
    seconds.'''

    number_samples = Int.T(xmltagname='NumberSamples')
    number_seconds = Int.T(xmltagname='NumberSeconds')


class Gain(Object):
    '''Complex type for sensitivity and frequency ranges. This complex
    type can be used to represent both overall sensitivities and
    individual stage gains. The FrequencyRangeGroup is an optional
    construct that defines a pass band in Hertz ( FrequencyStart and
    FrequencyEnd) in which the SensitivityValue is valid within the
    number of decibels specified in FrequencyDBVariation.'''

    def __init__(self, value=None, **kwargs):
        Object.__init__(self, value=value, **kwargs)

    value = Float.T(optional=True, xmltagname='Value')
    frequency = Float.T(optional=True, xmltagname='Frequency')


class NumeratorCoefficient(Object):
    i = Int.T(optional=True, xmlstyle='attribute')
    value = Float.T(xmlstyle='content')


class FloatNoUnit(Object):
    def __init__(self, value=None, **kwargs):
        Object.__init__(self, value=value, **kwargs)

    plus_error = Float.T(optional=True, xmlstyle='attribute')
    minus_error = Float.T(optional=True, xmlstyle='attribute')
    value = Float.T(xmlstyle='content')


class FloatWithUnit(FloatNoUnit):
    unit = String.T(optional=True, xmlstyle='attribute')


class Equipment(Object):
    resource_id = String.T(optional=True, xmlstyle='attribute')
    type = String.T(optional=True, xmltagname='Type')
    description = Unicode.T(optional=True, xmltagname='Description')
    manufacturer = Unicode.T(optional=True, xmltagname='Manufacturer')
    vendor = Unicode.T(optional=True, xmltagname='Vendor')
    model = Unicode.T(optional=True, xmltagname='Model')
    serial_number = String.T(optional=True, xmltagname='SerialNumber')
    installation_date = Timestamp.T(optional=True,
                                    xmltagname='InstallationDate')
    removal_date = Timestamp.T(optional=True, xmltagname='RemovalDate')
    calibration_date_list = List.T(Timestamp.T(xmltagname='CalibrationDate'))


class PhoneNumber(Object):
    description = Unicode.T(optional=True, xmlstyle='attribute')
    country_code = Int.T(optional=True, xmltagname='CountryCode')
    area_code = Int.T(xmltagname='AreaCode')
    phone_number = PhoneNumber.T(xmltagname='PhoneNumber')


class BaseFilter(Object):
    '''The BaseFilter is derived by all filters.'''

    resource_id = String.T(optional=True, xmlstyle='attribute')
    name = String.T(optional=True, xmlstyle='attribute')
    description = Unicode.T(optional=True, xmltagname='Description')
    input_units = Units.T(optional=True, xmltagname='InputUnits')
    output_units = Units.T(optional=True, xmltagname='OutputUnits')


class Sensitivity(Gain):
    '''Sensitivity and frequency ranges. The FrequencyRangeGroup is an
    optional construct that defines a pass band in Hertz
    (FrequencyStart and FrequencyEnd) in which the SensitivityValue is
    valid within the number of decibels specified in
    FrequencyDBVariation.'''

    input_units = Units.T(optional=True, xmltagname='InputUnits')
    output_units = Units.T(optional=True, xmltagname='OutputUnits')
    frequency_start = Float.T(optional=True, xmltagname='FrequencyStart')
    frequency_end = Float.T(optional=True, xmltagname='FrequencyEnd')
    frequency_db_variation = Float.T(optional=True,
                                     xmltagname='FrequencyDBVariation')


class Coefficient(FloatNoUnit):
    number = Counter.T(optional=True, xmlstyle='attribute')


class PoleZero(Object):
    '''Complex numbers used as poles or zeros in channel response.'''

    number = Int.T(optional=True, xmlstyle='attribute')
    real = FloatNoUnit.T(xmltagname='Real')
    imaginary = FloatNoUnit.T(xmltagname='Imaginary')

    def value(self):
        return self.real.value + 1J * self.imaginary.value


class ClockDrift(FloatWithUnit):
    unit = String.T(default='SECONDS/SAMPLE', optional=True,
                    xmlstyle='attribute')  # fixed


class Second(FloatWithUnit):
    '''A time value in seconds.'''

    unit = String.T(default='SECONDS', optional=True, xmlstyle='attribute')
    # fixed unit


class Voltage(FloatWithUnit):
    unit = String.T(default='VOLTS', optional=True, xmlstyle='attribute')
    # fixed unit


class Angle(FloatWithUnit):
    unit = String.T(default='DEGREES', optional=True, xmlstyle='attribute')
    # fixed unit


class Azimuth(FloatWithUnit):
    '''Instrument azimuth, degrees clockwise from North.'''

    unit = String.T(default='DEGREES', optional=True, xmlstyle='attribute')
    # fixed unit


class Dip(FloatWithUnit):
    '''Instrument dip in degrees down from horizontal. Together
    azimuth and dip describe the direction of the sensitive axis of
    the instrument.'''

    unit = String.T(default='DEGREES', optional=True, xmlstyle='attribute')
    # fixed unit


class Distance(FloatWithUnit):
    '''Extension of FloatWithUnit for distances, elevations, and depths.'''

    unit = String.T(default='METERS', optional=True, xmlstyle='attribute')
    # NOT fixed unit!


class Frequency(FloatWithUnit):
    unit = String.T(default='HERTZ', optional=True, xmlstyle='attribute')
    # fixed unit


class SampleRate(FloatWithUnit):
    '''Sample rate in samples per second.'''

    unit = String.T(default='SAMPLES/S', optional=True, xmlstyle='attribute')
    # fixed unit


class Person(Object):
    '''Representation of a person's contact information. A person can
    belong to multiple agencies and have multiple email addresses and
    phone numbers.'''

    name_list = List.T(Unicode.T(xmltagname='Name'))
    agency_list = List.T(Unicode.T(xmltagname='Agency'))
    email_list = List.T(Email.T(xmltagname='Email'))
    phone_list = List.T(PhoneNumber.T(xmltagname='Phone'))


class FIR(BaseFilter):
    '''Response: FIR filter. Corresponds to SEED blockette 61. FIR
    filters are also commonly documented using the Coefficients
    element.'''

    symmetry = Symmetry.T(xmltagname='Symmetry')
    numerator_coefficient_list = List.T(
        NumeratorCoefficient.T(xmltagname='NumeratorCoefficient'))


class Coefficients(BaseFilter):
    '''Response: coefficients for FIR filter. Laplace transforms or
    IIR filters can be expressed using type as well but the
    PolesAndZeros should be used instead. Corresponds to SEED
    blockette 54.'''

    cf_transfer_function_type = CfTransferFunction.T(
        xmltagname='CfTransferFunctionType')
    numerator_list = List.T(FloatWithUnit.T(xmltagname='Numerator'))
    denominator_list = List.T(FloatWithUnit.T(xmltagname='Denominator'))


class Latitude(FloatWithUnit):
    '''Type for latitude coordinate.'''

    unit = String.T(default='DEGREES', optional=True, xmlstyle='attribute')
    # fixed unit
    datum = String.T(default='WGS84', optional=True, xmlstyle='attribute')


class Longitude(FloatWithUnit):
    '''Type for longitude coordinate.'''

    unit = String.T(default='DEGREES', optional=True, xmlstyle='attribute')
    # fixed unit
    datum = String.T(default='WGS84', optional=True, xmlstyle='attribute')


class PolesZeros(BaseFilter):
    '''Response: complex poles and zeros. Corresponds to SEED
    blockette 53.'''

    pz_transfer_function_type = PzTransferFunction.T(
        xmltagname='PzTransferFunctionType')
    normalization_factor = Float.T(default=1.0,
                                   xmltagname='NormalizationFactor')
    normalization_frequency = Frequency.T(xmltagname='NormalizationFrequency')
    zero_list = List.T(PoleZero.T(xmltagname='Zero'))
    pole_list = List.T(PoleZero.T(xmltagname='Pole'))

    def get_pyrocko_response(self):
        if self.pz_transfer_function_type != 'LAPLACE (RADIANS/SECOND)':
            raise NoResponseInformation(
                'cannot convert PoleZero response of type %s' %
                self.pz_transfer_function_type)

        resp = trace.PoleZeroResponse(
            constant=self.normalization_factor,
            zeros=[z.value() for z in self.zero_list],
            poles=[p.value() for p in self.pole_list])

        computed_normalization_factor = self.normalization_factor / abs(
            resp.evaluate(num.array([self.normalization_frequency.value]))[0])

        perc = abs(computed_normalization_factor /
                   self.normalization_factor - 1.0) * 100

        if perc > 2.0:
            logger.warn(
                'computed and reported normalization factors differ by '
                '%.1f%%: computed: %g, reported: %g' % (
                    perc,
                    computed_normalization_factor,
                    self.normalization_factor))

        return resp


class ResponseListElement(Object):
    frequency = Frequency.T(xmltagname='Frequency')
    amplitude = FloatWithUnit.T(xmltagname='Amplitude')
    phase = Angle.T(xmltagname='Phase')


class Polynomial(BaseFilter):
    '''Response: expressed as a polynomial (allows non-linear sensors
    to be described). Corresponds to SEED blockette 62. Can be used to
    describe a stage of acquisition or a complete system.'''

    approximation_type = Approximation.T(default='MACLAURIN',
                                         xmltagname='ApproximationType')
    frequency_lower_bound = Frequency.T(xmltagname='FrequencyLowerBound')
    frequency_upper_bound = Frequency.T(xmltagname='FrequencyUpperBound')
    approximation_lower_bound = Float.T(xmltagname='ApproximationLowerBound')
    approximation_upper_bound = Float.T(xmltagname='ApproximationUpperBound')
    maximum_error = Float.T(xmltagname='MaximumError')
    coefficient_list = List.T(Coefficient.T(xmltagname='Coefficient'))


class Decimation(Object):
    '''Corresponds to SEED blockette 57.'''

    input_sample_rate = Frequency.T(xmltagname='InputSampleRate')
    factor = Int.T(xmltagname='Factor')
    offset = Int.T(xmltagname='Offset')
    delay = FloatWithUnit.T(xmltagname='Delay')
    correction = FloatWithUnit.T(xmltagname='Correction')


class Operator(Object):
    agency_list = List.T(Unicode.T(xmltagname='Agency'))
    contact_list = List.T(Person.T(xmltagname='Contact'))
    web_site = String.T(optional=True, xmltagname='WebSite')


class Comment(Object):
    '''Container for a comment or log entry. Corresponds to SEED
    blockettes 31, 51 and 59.'''

    id = Counter.T(optional=True, xmlstyle='attribute')
    value = Unicode.T(xmltagname='Value')
    begin_effective_time = Timestamp.T(optional=True,
                                       xmltagname='BeginEffectiveTime')
    end_effective_time = Timestamp.T(optional=True,
                                     xmltagname='EndEffectiveTime')
    author_list = List.T(Person.T(xmltagname='Author'))


class ResponseList(BaseFilter):
    '''Response: list of frequency, amplitude and phase values.
    Corresponds to SEED blockette 55.'''

    response_list_element_list = List.T(
        ResponseListElement.T(xmltagname='ResponseListElement'))


class Log(Object):
    '''Container for log entries.'''

    entry_list = List.T(Comment.T(xmltagname='Entry'))


class ResponseStage(Object):
    '''This complex type represents channel response and covers SEED
    blockettes 53 to 56.'''

    number = Counter.T(xmlstyle='attribute')
    resource_id = String.T(optional=True, xmlstyle='attribute')
    poles_zeros_list = List.T(
        PolesZeros.T(optional=True, xmltagname='PolesZeros'))
    coefficients_list = List.T(
        Coefficients.T(optional=True, xmltagname='Coefficients'))
    response_list = ResponseList.T(optional=True, xmltagname='ResponseList')
    fir = FIR.T(optional=True, xmltagname='FIR')
    polynomial = Polynomial.T(optional=True, xmltagname='Polynomial')
    decimation = Decimation.T(optional=True, xmltagname='Decimation')
    stage_gain = Gain.T(optional=True, xmltagname='StageGain')

    def get_pyrocko_response(self, nslc):
        responses = []
        if len(self.poles_zeros_list) == 1:
            pz = self.poles_zeros_list[0].get_pyrocko_response()
            responses.append(pz)

        elif len(self.poles_zeros_list) > 1:
            logger.warn(
                'multiple poles and zeros records in single response stage '
                '(%s.%s.%s.%s)' % nslc)
            for poles_zeros in self.poles_zeros_list:
                logger.warn('%s' % poles_zeros)

        elif (self.coefficients_list or
              self.response_list or
              self.fir or
              self.polynomial):

            pass
            # print 'unhandled response at stage %i' % self.number

        if self.stage_gain:
            responses.append(
                trace.PoleZeroResponse(constant=self.stage_gain.value))

        return responses

    @property
    def input_units(self):
        for e in (self.poles_zeros_list + self.coefficients_list +
                  [self.response_list, self.fir, self.polynomial]):
            if e is not None:
                return e.input_units

    @property
    def output_units(self):
        for e in (self.poles_zeros_list + self.coefficients_list +
                  [self.response_list, self.fir, self.polynomial]):
            if e is not None:
                return e.output_units


class Response(Object):
    resource_id = String.T(optional=True, xmlstyle='attribute')
    instrument_sensitivity = Sensitivity.T(optional=True,
                                           xmltagname='InstrumentSensitivity')
    instrument_polynomial = Polynomial.T(optional=True,
                                         xmltagname='InstrumentPolynomial')
    stage_list = List.T(ResponseStage.T(xmltagname='Stage'))

    def get_pyrocko_response(self, nslc, fake_input_units=None):
        responses = []
        for stage in self.stage_list:
            responses.extend(stage.get_pyrocko_response(nslc))

        if fake_input_units is not None:
            if self.instrument_sensitivity.input_units is None:
                raise NoResponseInformation('no input units given')

            input_units = self.instrument_sensitivity.input_units.name

            try:
                conresp = conversion[fake_input_units, input_units]
            except KeyError:
                raise NoResponseInformation(
                    'cannot convert between units: %s, %s'
                    % (fake_input_units, input_units))

            if conresp is not None:
                responses.append(conresp)

        return trace.MultiplyResponse(responses)


class BaseNode(Object):
    '''A base node type for derivation from: Network, Station and
    Channel types.'''

    code = String.T(xmlstyle='attribute')
    start_date = Timestamp.T(optional=True, xmlstyle='attribute')
    end_date = Timestamp.T(optional=True, xmlstyle='attribute')
    restricted_status = RestrictedStatus.T(optional=True, xmlstyle='attribute')
    alternate_code = String.T(optional=True, xmlstyle='attribute')
    historical_code = String.T(optional=True, xmlstyle='attribute')
    description = Unicode.T(optional=True, xmltagname='Description')
    comment_list = List.T(Comment.T(xmltagname='Comment'))

    def spans(self, *args):
        if len(args) == 0:
            return True
        elif len(args) == 1:
            return ((self.start_date is None or
                     self.start_date <= args[0]) and
                    (self.end_date is None or
                     args[0] <= self.end_date))

        elif len(args) == 2:
            return ((self.start_date is None or
                     args[1] >= self.start_date) and
                    (self.end_date is None or
                     self.end_date >= args[0]))


class Channel(BaseNode):
    '''Equivalent to SEED blockette 52 and parent element for the
    related the response blockettes.'''

    location_code = String.T(xmlstyle='attribute')
    external_reference_list = List.T(
        ExternalReference.T(xmltagname='ExternalReference'))
    latitude = Latitude.T(xmltagname='Latitude')
    longitude = Longitude.T(xmltagname='Longitude')
    elevation = Distance.T(xmltagname='Elevation')
    depth = Distance.T(xmltagname='Depth')
    azimuth = Azimuth.T(optional=True, xmltagname='Azimuth')
    dip = Dip.T(optional=True, xmltagname='Dip')
    type_list = List.T(Type.T(xmltagname='Type'))
    sample_rate = SampleRate.T(optional=True, xmltagname='SampleRate')
    sample_rate_ratio = SampleRateRatio.T(optional=True,
                                          xmltagname='SampleRateRatio')
    storage_format = String.T(optional=True, xmltagname='StorageFormat')
    clock_drift = ClockDrift.T(optional=True, xmltagname='ClockDrift')
    calibration_units = Units.T(optional=True, xmltagname='CalibrationUnits')
    sensor = Equipment.T(optional=True, xmltagname='Sensor')
    pre_amplifier = Equipment.T(optional=True, xmltagname='PreAmplifier')
    data_logger = Equipment.T(optional=True, xmltagname='DataLogger')
    equipment = Equipment.T(optional=True, xmltagname='Equipment')
    response = Response.T(optional=True, xmltagname='Response')

    @property
    def position_values(self):
        lat = self.latitude.value
        lon = self.longitude.value
        elevation = value_or_none(self.elevation)
        depth = value_or_none(self.depth)
        return lat, lon, elevation, depth


class Station(BaseNode):
    '''This type represents a Station epoch. It is common to only have
    a single station epoch with the station's creation and termination
    dates as the epoch start and end dates.'''

    latitude = Latitude.T(xmltagname='Latitude')
    longitude = Longitude.T(xmltagname='Longitude')
    elevation = Distance.T(xmltagname='Elevation')
    site = Site.T(optional=True, xmltagname='Site')
    vault = Unicode.T(optional=True, xmltagname='Vault')
    geology = Unicode.T(optional=True, xmltagname='Geology')
    equipment_list = List.T(Equipment.T(xmltagname='Equipment'))
    operator_list = List.T(Operator.T(xmltagname='Operator'))
    creation_date = Timestamp.T(optional=True, xmltagname='CreationDate')
    termination_date = Timestamp.T(optional=True, xmltagname='TerminationDate')
    total_number_channels = Counter.T(optional=True,
                                      xmltagname='TotalNumberChannels')
    selected_number_channels = Counter.T(optional=True,
                                         xmltagname='SelectedNumberChannels')
    external_reference_list = List.T(
        ExternalReference.T(xmltagname='ExternalReference'))
    channel_list = List.T(Channel.T(xmltagname='Channel'))

    @property
    def position_values(self):
        lat = self.latitude.value
        lon = self.longitude.value
        elevation = value_or_none(self.elevation)
        return lat, lon, elevation


class Network(BaseNode):
    '''This type represents the Network layer, all station metadata is
    contained within this element. The official name of the network or
    other descriptive information can be included in the Description
    element. The Network can contain 0 or more Stations.'''

    total_number_stations = Counter.T(optional=True,
                                      xmltagname='TotalNumberStations')
    selected_number_stations = Counter.T(optional=True,
                                         xmltagname='SelectedNumberStations')
    station_list = List.T(Station.T(xmltagname='Station'))

    @property
    def station_code_list(self):
        return sorted(set(s.code for s in self.station_list))

    @property
    def sl_code_list(self):
        sls = set()
        for station in self.station_list:
            for channel in station.channel_list:
                sls.add((station.code, channel.location_code))

        return sorted(sls)

    def summary(self, width=80, indent=4):
        sls = self.sl_code_list or [(x,) for x in self.station_code_list]
        lines = ['%s (%i):' % (self.code, len(sls))]
        if sls:
            ssls = ['.'.join(x for x in c if x) for c in sls]
            w = max(len(x) for x in ssls)
            n = (width - indent) / (w+1)
            while ssls:
                lines.append(
                    ' ' * indent + ' '.join(x.ljust(w) for x in ssls[:n]))

                ssls[:n] = []

        return '\n'.join(lines)


def value_or_none(x):
    if x is not None:
        return x.value
    else:
        return None


def pyrocko_station_from_channels(nsl, channels, inconsistencies='warn'):

    pos = lat, lon, elevation, depth = \
        channels[0].position_values

    if not all(pos == x.position_values for x in channels):
        info = '\n'.join(
            '    %s: %s' % (x.code, x.position_values) for
            x in channels)
    
        mess = 'encountered inconsistencies in channel ' \
               'lat/lon/elevation/depth ' \
               'for %s.%s.%s: \n%s' % (nsl + (info,))

        if inconsistencies == 'raise':
            raise InconsistentChannelLocations(mess)

        elif inconsistencies == 'warn':
            logger.warn(mess)
            logger.warn(' -> using mean values')

    apos = num.array([x.position_values for x in channels], dtype=num.float)
    mlat, mlon, mele, mdep = num.nansum(apos, axis=0) / num.sum(num.isfinite(apos), axis=0)

    pchannels = []
    for channel in channels:
        pchannels.append(model.Channel(
            channel.code,
            azimuth=value_or_none(channel.azimuth),
            dip=value_or_none(channel.dip)))

    return model.Station(
        *nsl,
        lat=mlat,
        lon=mlon,
        elevation=mele,
        depth=mdep,
        channels=pchannels)


class FDSNStationXML(Object):
    '''Top-level type for Station XML. Required field are Source
    (network ID of the institution sending the message) and one or
    more Network containers or one or more Station containers.'''

    schema_version = Float.T(default=1.0, xmlstyle='attribute')
    source = String.T(xmltagname='Source')
    sender = String.T(optional=True, xmltagname='Sender')
    module = String.T(optional=True, xmltagname='Module')
    module_uri = String.T(optional=True, xmltagname='ModuleURI')
    created = Timestamp.T(xmltagname='Created')
    network_list = List.T(Network.T(xmltagname='Network'))

    xmltagname = 'FDSNStationXML'

    def get_pyrocko_stations(self, nslcs=None, time=None, timespan=None,
                             inconsistencies='warn'):

        assert inconsistencies in ('raise', 'warn')

        tt = ()
        if time is not None:
            tt = (time,)
        elif timespan is not None:
            tt = timespan

        pstations = []
        for network in self.network_list:
            if not network.spans(*tt):
                continue

            for station in network.station_list:
                if not station.spans(*tt):
                    continue

                if station.channel_list:
                    loc_to_channels = {}
                    for channel in station.channel_list:
                        if not channel.spans(*tt):
                            continue

                        loc = channel.location_code.strip()
                        if loc not in loc_to_channels:
                            loc_to_channels[loc] = []

                        loc_to_channels[loc].append(channel)

                    for loc in sorted(loc_to_channels.keys()):
                        channels = loc_to_channels[loc]
                        if nslcs is not None:
                            channels = [channel for channel in channels 
                                        if (network.code, station.code, loc, channel.code) in nslcs]

                        if not channels:
                            continue

                        pos = lat, lon, elevation, depth = \
                            channels[0].position_values

                        nsl = network.code, station.code, loc
                        
                        pstations.append(
                            pyrocko_station_from_channels(nsl, channels, inconsistencies=inconsistencies))
                else:
                    pstations.append(model.Station(
                        network.code, station.code, '*',
                        lat=station.latitude.value,
                        lon=station.longitude.value,
                        elevation=value_or_none(station.elevation),
                        name=station.description or ''))

        return pstations

    def iter_network_stations(
            self, net=None, sta=None, time=None, timespan=None):

        tt = ()
        if time is not None:
            tt = (time,)
        elif timespan is not None:
            tt = timespan

        for network in self.network_list:
            if not network.spans(*tt) or (
                    net is not None and network.code != net):
                continue

            for station in network.station_list:
                if not station.spans(*tt) or (
                        sta is not None and station.code != sta):
                    continue

                yield (network, station)

    def iter_network_station_channels(
            self, net=None, sta=None, loc=None, cha=None,
            time=None, timespan=None):

        if loc is not None:
            loc = loc.strip()

        tt = ()
        if time is not None:
            tt = (time,)
        elif timespan is not None:
            tt = timespan

        for network in self.network_list:
            if not network.spans(*tt) or (
                    net is not None and network.code != net):
                continue

            for station in network.station_list:
                if not station.spans(*tt) or (
                        sta is not None and station.code != sta):
                    continue

                if station.channel_list:
                    for channel in station.channel_list:
                        if (not channel.spans(*tt) or
                                (cha is not None and channel.code != cha) or
                                (loc is not None and
                                 channel.location_code.strip() != loc)):
                            continue

                        yield (network, station, channel)

    def get_channel_groups(self, net=None, sta=None, loc=None, cha=None,
                           time=None, timespan=None):

        groups = {}
        for network, station, channel in self.iter_network_station_channels(
                net, sta, loc, cha, time=time, timespan=timespan):

            net = network.code
            sta = station.code
            cha = channel.code
            loc = channel.location_code.strip()
            if len(cha) == 3:
                bic = cha[:2]  # band and intrument code according to SEED
            elif len(cha) == 1:
                bic = ''
            else:
                bic = cha

            if channel.response and channel.response.instrument_sensitivity:
                unit = channel.response.instrument_sensitivity.input_units.name
            else:
                unit = None

            bic = (bic, unit)

            k = net, sta, loc
            if k not in groups:
                groups[k] = {}

            if bic not in groups[k]:
                groups[k][bic] = []

            groups[k][bic].append(channel)

        for nsl, bic_to_channels in groups.iteritems():
            bad_bics = []
            for bic, channels in bic_to_channels.iteritems():
                sample_rates = []
                for channel in channels:
                    sample_rates.append(channel.sample_rate.value)

                if not same(sample_rates):
                    scs = ','.join(channel.code for channel in channels)
                    srs = ', '.join('%e' % x for x in sample_rates)
                    err = 'ignoring channels with inconsistent sampling ' + \
                          'rates (%s.%s.%s.%s: %s)' % (nsl + (scs, srs))

                    logger.warn(err)
                    bad_bics.append(bic)

            for bic in bad_bics:
                del bic_to_channels[bic]

        return groups

    def choose_channels(
            self,
            target_sample_rate=None,
            priority_band_code=['H', 'B', 'M', 'L', 'V', 'E', 'S'],
            priority_units=['M/S', 'M/S**2'],
            priority_instrument_code=['H', 'L'],
            time=None,
            timespan=None):

        nslcs = {}
        for nsl, bic_to_channels in self.get_channel_groups(
                time=time, timespan=timespan).iteritems():

            useful_bics = []
            for bic, channels in bic_to_channels.iteritems():
                rate = channels[0].sample_rate.value

                if target_sample_rate is not None and \
                        rate < target_sample_rate*0.99999:
                    continue

                unit = bic[1]

                prio_unit = len(priority_units)
                try:
                    prio_unit = priority_units.index(unit)
                except ValueError:
                    pass

                prio_inst = len(priority_instrument_code)
                prio_band = len(priority_band_code)
                if len(channels[0].code) == 3:
                    try:
                        prio_inst = priority_instrument_code.index(
                            channels[0].code[1])
                    except ValueError:
                        pass

                    try:
                        prio_band = priority_band_code.index(
                            channels[0].code[0])
                    except ValueError:
                        pass

                if target_sample_rate is None:
                    rate = -rate

                useful_bics.append((-len(channels), prio_band, rate, prio_unit,
                                    prio_inst, bic))

            useful_bics.sort()

            for _, _, rate, _, _, bic in useful_bics:
                channels = sorted(bic_to_channels[bic])
                if channels:
                    for channel in channels:
                        nslcs[nsl + (channel.code,)] = channel

                    break

        return nslcs

    def get_pyrocko_response(
            self, nslc, time=None, timespan=None, fake_input_units=None):

        net, sta, loc, cha = nslc
        resps = []
        for _, _, channel in self.iter_network_station_channels(
                net, sta, loc, cha, time=time, timespan=timespan):
            resp = channel.response
            if resp:
                resps.append(resp.get_pyrocko_response(
                    nslc, fake_input_units=fake_input_units))

        if not resps:
            raise NoResponseInformation('%s.%s.%s.%s' % nslc)
        elif len(resps) > 1:
            raise MultipleResponseInformation('%s.%s.%s.%s' % nslc)

        return resps[0]

    @property
    def n_code_list(self):
        return sorted(set(x.code for x in self.network_list))

    @property
    def ns_code_list(self):
        nss = set()
        for network in self.network_list:
            for station in network.station_list:
                nss.add((network.code, station.code))

        return sorted(nss)

    @property
    def nsl_code_list(self):
        nsls = set()
        for network in self.network_list:
            for station in network.station_list:
                for channel in station.channel_list:
                    nsls.add(
                        (network.code, station.code, channel.location_code))

        return sorted(nsls)

    @property
    def nslc_code_list(self):
        nslcs = set()
        for network in self.network_list:
            for station in network.station_list:
                for channel in station.channel_list:
                    nslcs.add(
                        (network.code, station.code, channel.location_code,
                            channel.code))

        return sorted(nslcs)

    def summary(self):
        l = [
            'number of n codes: %i' % len(self.n_code_list),
            'number of ns codes: %i' % len(self.ns_code_list),
            'number of nsl codes: %i' % len(self.nsl_code_list),
            'number of nslc codes: %i' % len(self.nslc_code_list)
        ]

        return '\n'.join(l)


class InconsistentChannelLocations(Exception):
    pass


class InvalidRecord(Exception):
    def __init__(self, line):
        Exception.__init__(self)
        self._line = line

    def __str__(self):
        return 'Invalid record: "%s"' % self._line


def load_channel_table(stream):

    networks = {}
    stations = {}

    for line in stream:
        if line.startswith('#'):
            continue

        t = line.rstrip().split('|')

        if len(t) != 17:
            raise InvalidRecord(line)

        (net, sta, loc, cha, lat, lon, ele, dep, azi, dip, sens, scale,
            scale_freq, scale_units, sample_rate, start_date, end_date) = t

        try:
            if net not in networks:
                network = Network(code=net)
            else:
                network = networks[net]

            if (net, sta) not in stations:
                station = Station(
                    code=sta, latitude=lat, longitude=lon, elevation=ele)

                station.regularize()
            else:
                station = stations[net, sta]

            if scale:
                resp = Response(
                    instrument_sensitivity=Sensitivity(
                        value=scale,
                        frequency=scale_freq,
                        input_units=scale_units))
            else:
                resp = None

            channel = Channel(
                code=cha,
                location_code=loc.strip(),
                latitude=lat,
                longitude=lon,
                elevation=ele,
                depth=dep,
                azimuth=azi,
                dip=dip,
                sensor=Equipment(description=sens),
                response=resp,
                sample_rate=sample_rate,
                start_date=start_date,
                end_date=end_date or None)

            channel.regularize()

        except ValidationError:
            raise InvalidRecord(line)

        if net not in networks:
            networks[net] = network

        if (net, sta) not in stations:
            stations[net, sta] = station
            network.station_list.append(station)

        station.channel_list.append(channel)

    return FDSNStationXML(
        source='created from table input',
        created=time.time(),
        network_list=sorted(networks.values()))
