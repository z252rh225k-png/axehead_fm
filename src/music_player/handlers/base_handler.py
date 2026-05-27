from abc import ABC, abstractmethod

class BaseHandler(ABC):
    @abstractmethod
    def play(self, assets, state, hardware_dict):
        """
        Starts playback of the given assets using state and hardware references.
        """
        pass

    @abstractmethod
    def stop(self, state, hardware_dict):
        """
        Stops playback and cleans up handler-specific resources.
        """
        pass

    def update(self, state, hardware_dict):
        """
        Optional periodic update method called within the main loop.
        """
        pass
