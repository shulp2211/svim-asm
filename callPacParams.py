class callPacParams:
    def __init__(self):
        # Read tail mapping
        self.tail_span = 1000
        self.tail_min_mapq = 30
        self.tail_min_deviation = -0.02
        self.tail_max_deviation = 0.1

        # Counting
        self.count_win_size = 100
        self.count_k = 13
        self.count_band = 0.5

        # Find stretches
        self.stretch_threshold = 4
        self.stretch_tolerance = 2
        self.stretch_min_length = 3

        # Find best path through segments
        self.path_constant_gap_cost = 0
        self.path_linear_gap_cost = 0.01
        self.path_convex_gap_cost = 0
        self.path_root_gap_cost = 1
        self.path_tolerance = 2

        # Alignment
        self.align_costs = (3, -12, -12)

        # Read segments
        self.min_length = 50
        self.max_segment_gap_tolerance = 10
        self.max_deletion_size = 10000
        self.segment_overlap_tolerance = 5


    def set_with_options(self, options):
        # Read tail mapping        
        try:
            self.tail_span = options.tail_span
        except AttributeError:
            pass
        try:
            self.tail_min_mapq =  options.tail_min_mapq
        except AttributeError:
            pass
        try:
            self.tail_min_deviation = options.tail_min_deviation
        except AttributeError:
            pass
        try:
            self.tail_max_deviation = options.tail_max_deviation
        except AttributeError:
            pass

        # Counting
        try:
            self.count_win_size = options.count_win_size
        except AttributeError:
            pass
        try:
            self.count_k = options.count_k
        except AttributeError:
            pass
        try:
            self.count_band = options.count_band
        except AttributeError:
            pass

        # Find stretches
        try:
            self.stretch_threshold = options.stretch_threshold
        except AttributeError:
            pass
        try:
            self.stretch_tolerance = options.stretch_tolerance
        except AttributeError:
            pass
        try:
            self.stretch_min_length = options.stretch_min_length
        except AttributeError:
            pass

        # Find best path through segments
        try:
            self.path_constant_gap_cost = options.path_constant_gap_cost
        except AttributeError:
            pass
        try:
            self.path_linear_gap_cost = options.path_linear_gap_cost
        except AttributeError:
            pass
        try:
            self.path_convex_gap_cost = options.path_convex_gap_cost
        except AttributeError:
            pass
        try:
            self.path_root_gap_cost = options.path_root_gap_cost
        except AttributeError:
            pass
        try:
            self.path_tolerance = options.path_tolerance
        except AttributeError:
            pass

        # Alignment
        try:
            self.align_costs = (options.align_costs_match, options.align_costs_mismatch, options.align_costs_gap)
        except AttributeError:
            pass

        # Read segments
        try:
            self.min_length = options.min_length
        except AttributeError:
            pass
        try:
            self.max_segment_gap_tolerance = options.max_segment_gap_tolerance
        except AttributeError:
            pass
        try:
            self.max_deletion_size = options.max_deletion_size
        except AttributeError:
            pass
        try:
            self.segment_overlap_tolerance = options.segment_overlap_tolerance
        except AttributeError:
            pass
